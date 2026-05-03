# e2e

Playwright smoke for the SPA. Boots `evalbox web` and walks the
Setup → Running → Results flow against a route-intercepted backend
(no real model calls).

## Prerequisites

```bash
pip install -e ".[web]"
cd web_src && pnpm install && pnpm build
python scripts/build_frontend.py     # publishes the bundle into the package

cd e2e
pnpm install
pnpm install-browsers                # downloads Chromium for Playwright
```

## Run

```bash
cd e2e
pnpm test
```

The default port is 8765. Override with `EVALBOX_E2E_PORT`. To run
against an already-running server, set `EVALBOX_E2E_NO_SERVER=1`.
