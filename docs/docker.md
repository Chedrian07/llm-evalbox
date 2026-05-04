# Running llm-evalbox in Docker

## Quick start

```bash
cp .env.example .env
# fill in EVALBOX_BASE_URL / EVALBOX_MODEL / OPENAI_API_KEY (or whichever key env)
docker compose up -d --build
open http://127.0.0.1:8765
```

The first run builds the image (multi-stage: Node 20 → Python 3.12-slim,
~280 MB). Subsequent runs reuse the build cache.

## What lives where

| Path on host           | Path in container | What                                            |
|------------------------|-------------------|-------------------------------------------------|
| `./data/`              | `/data/`          | `cache/` (response cache) + `config/` + `runs.sqlite` (history, learned capabilities, profiles) |
| `./evalbox-runs/`      | `/app/evalbox-runs/` | Per-run `result.json` + `result.questions.jsonl` |
| `./.env`               | `EVALBOX_*` env   | Loaded via `env_file` — same shape as host CLI  |

`runs.sqlite` is a single SQLite file holding **history + learned
capabilities + profiles** in separate tables. Wipe it to reset all
remembered state at once.

## Talking to a host-local LLM (vLLM / SGLang / Ollama / …)

If you set `EVALBOX_BASE_URL=http://localhost:8000/v1`, the container
can't reach the host's loopback by default. The compose file fixes
this on every platform:

- **macOS / Windows (Docker Desktop)**: `host.docker.internal` is
  resolved natively. Our backend rewrites `localhost` → that name
  automatically inside the container, so `localhost:8000` keeps working.
- **Linux**: `extra_hosts: ["host.docker.internal:host-gateway"]` in
  `docker-compose.yml` exposes the same name, so the same rewrite
  applies.

The user-facing URL stays `localhost` in your `.env` and the SPA
input. The connection card shows a small chip
(`Rewrote localhost → http://host.docker.internal:8000/v1`) the first
time you hit `Test connection`, so you know where the call actually
went.

To opt out, set `EVALBOX_LOCALHOST_REWRITE=off` in `.env`.

## Bind-token

Inside the container the server binds `0.0.0.0:8765`. The `--bind-token`
guard (cli.py:659) refuses to start without a token, so the entrypoint
generates a 32-char random hex token if you didn't supply one:

```text
evalbox: bind-token=03f4…
```

Grab it from `docker logs llm-evalbox` and pass it as the
`x-evalbox-token` header on protected `/api/*` calls. `GET /api/health`
stays public so Docker can run its healthcheck.

For browser use, open the printed `browser-bootstrap=...` URL once. It
sets an HttpOnly same-origin cookie and then redirects back to `/`, so
the SPA's fetch and EventSource calls authenticate without exposing the
token to JavaScript. A plain `GET /` does not mint a cookie; this keeps a
host-network exposure from becoming "visit the homepage to unlock the
API".

To use a fixed token instead, set `EVALBOX_WEB_BIND_TOKEN=...` in
`.env`.

## Sandbox tiers in a container

| Tier | In Docker? | Notes |
|------|------------|-------|
| 1 — subprocess + RLIMIT | ✅ | Works out of the box. RLIMIT_AS / RLIMIT_CPU enforced by the Linux kernel. |
| 2 — docker (DinD) | ⚠️ out of scope | Would need `/var/run/docker.sock` mounted + `docker` CLI in the image. Not bundled. |
| 3 — e2b cloud | ✅ | Set `E2B_API_KEY` in `.env`; no local sandbox needed. |

## Building manually

```bash
docker build -t llm-evalbox:dev .
docker run --rm \
    -p 127.0.0.1:8765:8765 \
    --add-host=host.docker.internal:host-gateway \
    -v $PWD/data:/data \
    -v $PWD/evalbox-runs:/app/evalbox-runs \
    --env-file .env \
    llm-evalbox:dev
```

## Verifying

```bash
curl -fsS http://127.0.0.1:8765/api/health
# {"status":"ok","version":"..."}
```

## Wiping state

```bash
docker compose down
rm -rf ./data ./evalbox-runs
```

## CLI inside the container

The image ships the same `evalbox` CLI:

```bash
docker compose exec evalbox evalbox --help
docker compose exec evalbox evalbox doctor --base-url http://host.docker.internal:8000/v1 --model my-model
docker compose exec evalbox evalbox capabilities ls
```
