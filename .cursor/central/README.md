# Sunny — Fleet (global) dashboard

A tiny, dependency-free **collector** that aggregates progress from many
**independent VPS runs** into one **global dashboard** on a central domain.

## Same agents everywhere

Every worker VPS uses the **same** `.cursor/` agent definitions (clone this
repo or symlink `.cursor/` into each project). Each VPS is a fully independent
run — its own project, domain, `.env`, `.sunny/`, and auto-generated `RUN_ID`.
The only shared configuration across VPSs is the **fleet domain** — workers auto-fetch the push token from `/api/fleet-config`.

```
                    ┌── VPS #1 (project A, domain a.com) ── same .cursor/ agents
CENTRAL domain ◄────├── VPS #2 (project B, domain b.com) ── same .cursor/ agents
(global.html)       └── VPS #3 (project C, domain c.com) ── same .cursor/ agents
     ▲                        each pushes progress.json (Bearer token)
     └── deploy .cursor/central/ here ONCE
```

Each VPS keeps its own local dashboard (`agentprogress.html`) and additionally
**pushes** its `progress.json` here after every handoff. This page shows one
**card per run** — project, VPS, % complete, current stage, ETA, and any
**"action required"** items (e.g. an external API key a run is waiting on) —
with a link to that VPS's full dashboard.

```
VPS #1 ─┐
VPS #2 ─┼─ POST /api/runs/<runId>  ──►  central domain  ──►  you (one fleet view)
VPS #3 ─┘   (Bearer token)              global.html + collector
```

## What's here

| File | Purpose |
| --- | --- |
| `collector.py` | Stdlib HTTP server: auto token, `GET /api/fleet-config`, `POST /api/runs/<id>`, `GET /api/runs`, serves `global.html`. Covered by `test_collector.py`. |
| `global.html` | The fleet dashboard (auto-refresh, cards per run, action-required badges). |
| `Dockerfile` | Builds the collector image (python:3.12-alpine). |
| `docker-compose.yml` | Collector + Nginx (TLS) for the central domain. |
| `nginx-central.conf` | Reverse proxy + ACME challenge + HTTPS. |
| `.env.example` | `CENTRAL_DOMAIN`, `ACME_EMAIL`, `COLLECTOR_TOKENS`. |

## Deploy — option 1: let an agent do it (recommended)

On the host that owns the fleet domain, invoke the **Fleet Host Agent (Hari)** — it runs every step below for you (config, cert, stack, renewal, validation) and is idempotent:

> Sunny, set up the fleet dashboard host. Fleet domain: `fleet.example.com` (admin@example.com).

You still need the **DNS A record** (`fleet.example.com` → this host) and ports 80/443 open — Hari checks these and tells you if they're missing. See [`.cursor/agents/fleet-host-agent.md`](../agents/fleet-host-agent.md).

## Deploy — option 2: manual (on the central host)

1. **DNS:** point `CENTRAL_DOMAIN` (e.g. `fleet.example.com`) A-record at this host; open ports 80 + 443.
2. **Config** (fleet domain + email only — no token to generate):
   ```bash
   cp .env.example .env
   # set CENTRAL_DOMAIN and ACME_EMAIL (or default admin@<CENTRAL_DOMAIN>)
   ```
3. **Issue the TLS cert first** (the Nginx HTTPS block needs it to exist before it starts, so do this with the stack down and port 80 free):
   ```bash
   set -a; . ./.env; set +a            # load CENTRAL_DOMAIN / ACME_EMAIL
   docker run --rm -p 80:80 \
     -v "$PWD/letsencrypt:/etc/letsencrypt" \
     certbot/certbot certonly --standalone \
     -d "$CENTRAL_DOMAIN" --email "$ACME_EMAIL" --agree-tos --no-eff-email
   ```
4. **Start the stack** (Nginx now finds the cert and serves HTTPS):
   ```bash
   docker compose up -d --build
   ```
5. **Renewal** — brief reload, runs from cron/systemd:
   ```bash
   docker run --rm -p 80:80 -v "$PWD/letsencrypt:/etc/letsencrypt" \
     certbot/certbot renew --standalone \
     --pre-hook "docker compose stop nginx" --post-hook "docker compose start nginx"
   ```
   (Certs renew well before expiry; the dashboard is unavailable only for the few seconds Nginx restarts.)

Now `https://<CENTRAL_DOMAIN>/` shows the fleet; `GET /api/runs` is the JSON feed; `GET /api/fleet-config` exposes the auto-generated push token for worker agents.

The compose deployment stores collector state in the `collector-data` Docker volume mounted at `/data` inside the collector container. The direct HTTP fallback in `fleet-host-agent.md` uses host `./data:/data` so it can reuse the same token when you later cut over to HTTPS.

## Worker VPSs (agents do everything)

You **do not** copy tokens or edit `.env` by hand. At Sunny kickoff on each worker VPS, give only:

- **Project domain** (this app's domain)
- **Fleet domain** (this collector's `CENTRAL_DOMAIN`)

Maya on each worker:
1. Writes `CENTRAL_DASHBOARD_URL=https://<fleet-domain>` to `.env`
2. Fetches `CENTRAL_PUSH_TOKEN` from `GET https://<fleet-domain>/api/fleet-config`
3. Auto-generates `RUN_ID`, all DB/JWT secrets, and `ACME_EMAIL` (`admin@<project-domain>` unless you gave an email)
4. Pushes after every handoff:

```bash
curl -fsS -X POST "$CENTRAL_DASHBOARD_URL/api/runs/$RUN_ID" \
  -H "Authorization: Bearer $CENTRAL_PUSH_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @.sunny/web/progress.json
```

The push is **best-effort**: if the fleet host is down, the local run continues and retries on the next handoff.

## Scope: visibility only (not HA)

This collector is a **progress visibility board**, not a high-availability or control-plane service. It aggregates status snapshots so you can watch many runs in one place. It is intentionally simple (single container, file-backed, no clustering/replication). If it goes down, **worker runs are unaffected** — they keep building locally and retry the best-effort push on the next handoff. Don't put anything load-bearing behind it, and don't treat its data as a system of record.

## Security (production-hardened)

- Writes (`POST /api/runs/<id>`) require a valid **Bearer token**. `runId` is sanitized server-side (no path traversal); POST bodies are size-capped; per-IP **rate limiting** (`limit_req`) on the edge.
- **Modern TLS only** (TLS 1.2/1.3, Mozilla-intermediate ciphers, OCSP stapling, `ssl_session_tickets off`).
- **Security headers** on every response: HSTS (2y, includeSubDomains), `X-Content-Type-Options`, `X-Frame-Options: DENY`, a locked-down `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`. The collector also emits nosniff / frame-deny so the TLS-less fallback stays safe.
- **Least privilege:** the collector image runs as a **non-root** user; both services use `no-new-privileges`; only Nginx publishes 80/443 (the collector's 8080 is internal). Log rotation is capped (json-file, 10m × 5).
- Tokens and `.env` are **gitignored**. On first start the collector **auto-generates** a push token and saves it under `DATA_DIR` (`/data/fleet_push.token` in the compose container; host `./data/fleet_push.token` only for the direct HTTP fallback). Workers fetch it via `/api/fleet-config` — you never distribute it manually. To rotate: set `COLLECTOR_TOKENS` explicitly and restart.

## Local collector tests

Run the stdlib smoke tests without Docker:

```bash
python .cursor/central/test_collector.py
```

They verify token bootstrap, authenticated writes, run listing, and run ID sanitization.

### Exposure model — read this before exposing it to the internet

By default, **reads are public**: the dashboard (`/`, `/api/runs`) and **`/api/fleet-config`** are open. `/api/fleet-config` returns the push token so worker agents can self-configure with zero manual setup. That token is **push-only** (it lets a caller upload status snapshots — it grants no read access and no code execution), but a public `/api/fleet-config` means **anyone who can reach the URL can fetch it and POST runs**. On a private network or low-sensitivity setup that's a fine trade for zero-config workers. If the fleet domain is **internet-facing**, harden it:

- **Option A — make the board private, keep workers zero-config (recommended).** Put **Basic-Auth on the human routes only** (`/` and `/api/runs`), leaving `/api/fleet-config` + `POST /api/runs/<id>` open for workers (still Bearer-protected for writes, still rate-limited). The dashboard then needs a password to view, while workers are unchanged. Location-scoped example is in `nginx-central.conf` (commented).
- **Option B — full lockdown.** Restrict `/api/fleet-config` and `POST /api/runs/` to your worker VPS IPs with an Nginx `allow`/`deny` allowlist (or a private network/VPN), and Basic-Auth the dashboard. Most secure; requires knowing worker IPs.
- **Rotate the token** any time: set `COLLECTOR_TOKENS=<new>` in `.env` and restart; workers re-fetch on their next push (or pin IPs as above).
