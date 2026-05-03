# SPDX-License-Identifier: Apache-2.0
"""FastAPI app + uvicorn launcher.

The SPA is served from `llm_evalbox/web/frontend/` (built by
`scripts/build_frontend.py`). When the directory is missing — the
front-end hasn't been built yet — we still expose the API and serve a
short text placeholder at `/`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from llm_evalbox._version import __version__
from llm_evalbox.web.routes.benchmarks import router as benchmarks_router
from llm_evalbox.web.routes.connection import router as connection_router
from llm_evalbox.web.routes.history import router as history_router
from llm_evalbox.web.routes.models import router as models_router
from llm_evalbox.web.routes.pricing import router as pricing_router
from llm_evalbox.web.routes.runs import router as runs_router
from llm_evalbox.web.routes.shares import router as shares_router

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"

_PLACEHOLDER_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>llm-evalbox</title>
<style>body{font-family:system-ui,sans-serif;max-width:42em;margin:3em auto;padding:0 1em;color:#333}
code{background:#f3f3f3;padding:2px 6px;border-radius:3px}
.api{margin-top:1em}.api li{margin:.3em 0}</style></head>
<body>
<h1>llm-evalbox API</h1>
<p>The SPA bundle hasn't been built yet. Run:</p>
<pre>cd web_src && pnpm install && pnpm build
python scripts/build_frontend.py</pre>
<p>The HTTP API is up regardless:</p>
<ul class="api">
<li><code>GET  /api/health</code></li>
<li><code>POST /api/connection/test</code></li>
<li><code>GET  /api/models?base_url=…&amp;adapter=…</code></li>
<li><code>GET  /api/benchmarks</code></li>
<li><code>POST /api/pricing/estimate</code></li>
<li><code>POST /api/runs</code> &mdash; <code>GET /api/runs/{id}/events</code> (SSE)</li>
</ul></body></html>
"""


def _bind_token_required(host: str) -> str | None:
    """Return the required token if the host is non-loopback."""
    if host in ("127.0.0.1", "::1", "localhost"):
        return None
    token = os.environ.get("EVALBOX_WEB_BIND_TOKEN")
    return token or ""


def build_app(*, bind_token: str | None = None) -> FastAPI:
    app = FastAPI(
        title="llm-evalbox",
        version=__version__,
        description="Run academic benchmarks against any OpenAI-compatible endpoint.",
    )

    # Same-origin only; relax for dev when EVALBOX_WEB_DEV=1.
    if os.environ.get("EVALBOX_WEB_DEV") == "1":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if bind_token:
        @app.middleware("http")
        async def _check_token(request, call_next):
            # Allow GET on root and health for sanity checks; require token elsewhere.
            if request.url.path.startswith("/api/"):
                supplied = request.headers.get("x-evalbox-token", "")
                if supplied != bind_token:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=401, content={"detail": "missing or bad X-Evalbox-Token"})
            return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(connection_router)
    app.include_router(models_router)
    app.include_router(benchmarks_router)
    app.include_router(pricing_router)
    app.include_router(runs_router)
    app.include_router(shares_router)
    app.include_router(history_router)

    if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
        # Mount the SPA under "/". The catch-all path must come last so the
        # /api/* routes still win.
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="spa")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def root_placeholder() -> str:
            return _PLACEHOLDER_HTML

    return app


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    bind_token: str | None = None,
    reload: bool = False,
) -> None:
    import uvicorn
    app = build_app(bind_token=bind_token)
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")
