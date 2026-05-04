# syntax=docker/dockerfile:1.6
#
# llm-evalbox single-image build. Two stages:
#   1. `frontend` — node:20-alpine builds the SPA at web_src/ and writes
#      `dist/` artifacts. We prebuild here so the runtime stage doesn't
#      carry node_modules or any toolchain.
#   2. `runtime` — python:3.12-slim installs the package with web extras
#      and copies the SPA bundle into `llm_evalbox/web/frontend/`. The
#      hatch hook is bypassed via EVALBOX_SKIP_FRONTEND=1 so we don't
#      try to re-run pnpm in the python image.
#
# Single user (uid 1000, name `app`). State lives under /data
# (EVALBOX_DATA_DIR) so a single host bind covers cache + config +
# learned capabilities + history. Run output writes to /app/evalbox-runs.
#
# Build:
#   docker build -t llm-evalbox:dev .
# Run:
#   docker run --rm -p 127.0.0.1:8765:8765 \
#              -v $PWD/data:/data \
#              -v $PWD/evalbox-runs:/app/evalbox-runs \
#              --env-file .env \
#              llm-evalbox:dev
# (or use docker-compose.yml — preferred, sets extra_hosts for Linux too)

# ---------- stage 1: build the SPA ----------
FROM node:20-alpine AS frontend

WORKDIR /web

# Enable corepack so pnpm matches the project's lockfile resolver.
RUN corepack enable

# Copy only the manifest first to maximise the layer cache hit when
# source files change but deps don't.
COPY web_src/package.json web_src/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Now copy the rest and build.
COPY web_src/. ./
RUN pnpm build


# ---------- stage 2: python runtime ----------
FROM python:3.12-slim AS runtime

# curl is only needed for HEALTHCHECK; everything else is pure Python.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Non-root user. uid 1000 lines up with most desktop Linux setups so a
# bind-mounted ./data directory ends up owned by the same user on host.
RUN useradd --uid 1000 --create-home --shell /bin/bash app

WORKDIR /app

# Skip the hatch frontend build hook — we already built the SPA in
# stage 1 and will copy it in below.
ENV EVALBOX_SKIP_FRONTEND=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install Python deps. We copy the package source first because the
# wheel build (via hatch) needs the package on disk, and the bundled
# datasets (~62MB) are part of the package layout via force-include.
COPY pyproject.toml README.md ./
COPY llm_evalbox ./llm_evalbox
COPY scripts ./scripts

# Pull the SPA build from stage 1 BEFORE pip install so the hatch
# force-include can pick it up if the wheel is rebuilt later.
COPY --from=frontend /web/dist ./llm_evalbox/web/frontend

RUN pip install --upgrade pip \
 && pip install ".[web]"

# Stage the runtime user's data directory and run-output directory.
# /data is intended to be bind-mounted; we just create the mount point
# with the right ownership so non-root writes don't get EACCES.
RUN mkdir -p /data /app/evalbox-runs \
 && chown -R app:app /data /app/evalbox-runs /app

USER app

# Container-aware defaults. Users can override via env_file or
# `docker run -e ...`.
ENV EVALBOX_IN_DOCKER=1 \
    EVALBOX_WEB_HOST=0.0.0.0 \
    EVALBOX_WEB_PORT=8765 \
    EVALBOX_DATA_DIR=/data \
    EVALBOX_LOCALHOST_REWRITE=auto

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8765/api/health || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["web"]
