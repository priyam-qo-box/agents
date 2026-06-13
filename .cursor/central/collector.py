#!/usr/bin/env python3
"""Sunny fleet collector — central aggregation point for many independent VPS runs.

Dependency-free (Python 3.8+ stdlib only). Each VPS's Maya pushes its progress
here after every handoff; the global dashboard reads it back.

Endpoints
---------
  GET  /api/fleet-config   Public. Returns push URL + token for worker VPS agents.
  POST /api/runs/<runId>   Bearer-token auth. Body = JSON run snapshot. Upserts.
  GET  /api/runs           Public. Summary array of all runs.
  GET  /api/runs/<runId>   Public. Full snapshot for one run.
  GET  /healthz            Public. Liveness.
  GET  / , /global.html    Public. Fleet dashboard.

Config (env)
------------
  COLLECTOR_TOKEN / COLLECTOR_TOKENS   Optional. If unset, a strong token is
                                       auto-generated on first start and saved
                                       to DATA_DIR/fleet_push.token (workers
                                       fetch it via GET /api/fleet-config).
  CENTRAL_DOMAIN                       Fleet hostname (for fleet-config response).
  DATA_DIR, PORT, STALE_AFTER_MIN, MAX_BODY_BYTES

Security notes
--------------
  - The push token allows status uploads only. Reads are public (status page).
  - Put the fleet view behind Nginx Basic-Auth if you want it private.
  - runId is sanitized server-side (no path traversal).
"""

import json
import os
import re
import secrets
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "data"))
RUNS_DIR = os.path.join(DATA_DIR, "runs")
FLEET_TOKEN_FILE = os.path.join(DATA_DIR, "fleet_push.token")
PORT = int(os.environ.get("PORT", "8080"))
STALE_AFTER_MIN = int(os.environ.get("STALE_AFTER_MIN", "15"))
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(1024 * 1024)))
GLOBAL_HTML = os.path.join(HERE, "global.html")
CENTRAL_DOMAIN = (os.environ.get("CENTRAL_DOMAIN") or "").strip()

_RUNID_RE = re.compile(r"[^A-Za-z0-9._-]")
_BOOTSTRAPPED_TOKEN = None


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_run_id(raw):
    rid = _RUNID_RE.sub("-", (raw or "").strip())[:128]
    return rid or None


def _ensure_dirs():
    os.makedirs(RUNS_DIR, exist_ok=True)


def _load_persisted_token():
    try:
        if os.path.isfile(FLEET_TOKEN_FILE):
            with open(FLEET_TOKEN_FILE, "r", encoding="utf-8") as fh:
                t = fh.read().strip()
                if t:
                    return t
    except Exception:
        pass
    return None


def _persist_token(token):
    _ensure_dirs()
    tmp = FLEET_TOKEN_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(token)
    os.replace(tmp, FLEET_TOKEN_FILE)


def _bootstrap_fleet_token():
    """Auto-generate and persist a push token when none is configured."""
    global _BOOTSTRAPPED_TOKEN
    if _BOOTSTRAPPED_TOKEN:
        return _BOOTSTRAPPED_TOKEN
    existing = _load_persisted_token()
    if existing:
        _BOOTSTRAPPED_TOKEN = existing
        return existing
    token = secrets.token_urlsafe(32)
    _persist_token(token)
    _BOOTSTRAPPED_TOKEN = token
    print("[collector] auto-generated fleet push token (saved to %s)" % FLEET_TOKEN_FILE)
    print("[collector] workers fetch via GET /api/fleet-config — no manual token setup")
    return token


def _tokens():
    toks = set()
    if os.environ.get("COLLECTOR_TOKEN"):
        toks.add(os.environ["COLLECTOR_TOKEN"].strip())
    for t in (os.environ.get("COLLECTOR_TOKENS", "")).split(","):
        t = t.strip()
        if t and t != "change-me-generate-with-openssl":
            toks.add(t)
    if not toks:
        toks.add(_bootstrap_fleet_token())
    return toks


def _fleet_config_payload():
    domain = CENTRAL_DOMAIN or "localhost"
    base = "https://%s" % domain if not domain.startswith("http") else domain.rstrip("/")
    token = next(iter(_tokens()))
    return {
        "schema": 1,
        "centralDomain": domain,
        "dashboardUrl": base + "/",
        "pushUrl": base + "/api/runs/<runId>",
        "fleetConfigUrl": base + "/api/fleet-config",
        "token": token,
        "generatedAt": _now_iso(),
    }


def _summarize(run):
    actions = run.get("actionRequired") or []
    if not isinstance(actions, list):
        actions = []
    received = run.get("receivedAt") or run.get("generatedAt")
    stale = False
    try:
        ts = datetime.strptime(received, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        stale = (datetime.now(timezone.utc) - ts).total_seconds() > STALE_AFTER_MIN * 60
    except Exception:
        pass
    counts = run.get("counts") or {}
    return {
        "runId": run.get("runId"),
        "project": run.get("project") or {},
        "vps": run.get("vps") or "",
        "localDashboardUrl": run.get("localDashboardUrl") or "",
        "status": run.get("status") or "unknown",
        "phase": run.get("phase") or "",
        "currentStageLabel": run.get("currentStageLabel") or "",
        "counts": {"done": counts.get("done", 0), "total": counts.get("total", 0)},
        "timeConsumedMs": run.get("timeConsumedMs", 0),
        "estimatedRemainingMs": run.get("estimatedRemainingMs", 0),
        "eta": run.get("eta") or "",
        "actionCount": len(actions),
        "actionRequired": actions[:20],
        "generatedAt": run.get("generatedAt") or "",
        "receivedAt": received or "",
        "stale": stale,
    }


def _load_all():
    _ensure_dirs()
    out = []
    for name in os.listdir(RUNS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(RUNS_DIR, name), "r", encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "SunnyCollector/1.1"

    def _send(self, code, payload=None, ctype="application/json", raw=None):
        body = raw if raw is not None else (json.dumps(payload).encode("utf-8") if payload is not None else b"")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Defense-in-depth headers (also cover the TLS-less fallback, where the
        # collector is exposed directly without Nginx in front).
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        # Public, read-only JSON feed — CORS open for the GET API only.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorized(self):
        hdr = self.headers.get("Authorization", "")
        if hdr.startswith("Bearer "):
            return hdr[7:].strip() in _tokens()
        return False

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self._send(200, {"ok": True, "time": _now_iso()})
        if path == "/api/fleet-config":
            return self._send(200, _fleet_config_payload())
        if path == "/api/runs":
            runs = sorted(
                (_summarize(r) for r in _load_all()),
                key=lambda s: s.get("receivedAt") or "",
                reverse=True,
            )
            return self._send(200, {"generatedAt": _now_iso(), "count": len(runs), "runs": runs})
        if path.startswith("/api/runs/"):
            rid = _safe_run_id(path[len("/api/runs/"):])
            fp = os.path.join(RUNS_DIR, rid + ".json") if rid else None
            if fp and os.path.isfile(fp):
                with open(fp, "rb") as fh:
                    return self._send(200, raw=fh.read())
            return self._send(404, {"error": "not found"})
        if path in ("/", "/global.html", "/index.html"):
            if os.path.isfile(GLOBAL_HTML):
                with open(GLOBAL_HTML, "rb") as fh:
                    return self._send(200, raw=fh.read(), ctype="text/html; charset=utf-8")
            return self._send(404, raw=b"global.html missing", ctype="text/plain")
        return self._send(404, {"error": "not found"})

    do_HEAD = do_GET

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/runs/"):
            return self._send(404, {"error": "not found"})
        if not self._authorized():
            return self._send(401, {"error": "missing or invalid bearer token"})
        rid = _safe_run_id(path[len("/api/runs/"):])
        if not rid:
            return self._send(400, {"error": "invalid runId"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, {"error": "bad content-length"})
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send(413, {"error": "body too large or empty"})
        raw = self.rfile.read(length)
        try:
            run = json.loads(raw.decode("utf-8"))
            if not isinstance(run, dict):
                raise ValueError("body must be a JSON object")
        except Exception as exc:
            return self._send(400, {"error": "invalid JSON: %s" % exc})
        run["runId"] = rid
        run["receivedAt"] = _now_iso()
        _ensure_dirs()
        tmp = os.path.join(RUNS_DIR, rid + ".json.tmp")
        final = os.path.join(RUNS_DIR, rid + ".json")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(run, fh)
        os.replace(tmp, final)
        return self._send(200, {"ok": True, "runId": rid, "receivedAt": run["receivedAt"]})


def main():
    _ensure_dirs()
    _tokens()  # bootstrap token file if needed
    print("[collector] data dir: %s" % DATA_DIR)
    if CENTRAL_DOMAIN:
        print("[collector] central domain: %s" % CENTRAL_DOMAIN)
    print("[collector] fleet-config: GET /api/fleet-config")
    print("[collector] listening on 0.0.0.0:%d" % PORT)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
