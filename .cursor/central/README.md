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
| `collector.py` | Stdlib HTTP server: auto token, `GET /api/fleet-config`, `POST /api/runs/<id>`, `GET /api/runs`, serves `global.html`. Smoke-tested end-to-end. |
| `global.html` | The fleet dashboard (auto-refresh, cards per run, action-required badges). |
| `Dockerfile` | Builds the collector image (python:3.12-alpine). |
| `docker-compose.yml` | Collector + Nginx (TLS) for the central domain. |
| `nginx-central.conf` | Reverse proxy + ACME challenge + HTTPS. |
| `.env.example` | `CENTRAL_DOMAIN`, `ACME_EMAIL`, `COLLECTOR_TOKENS`. |

## Deploy (on the central host)

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

## Security

- Writes require a valid **Bearer token**; reads (`/api/runs`, dashboard) are public.
  To make the fleet view private too, enable Nginx **Basic-Auth** (commented in `nginx-central.conf`).
- `runId` is sanitized server-side (no path traversal); POST bodies are size-capped.
- Tokens and `.env` are **gitignored**. On first start the collector **auto-generates** a push token (saved to `data/fleet_push.token`). Workers fetch it via `/api/fleet-config` — you never distribute it manually. To rotate: set `COLLECTOR_TOKENS` explicitly and restart.
