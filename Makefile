# llm-evalbox developer convenience targets.
#
# Quick start:
#   make up      compose up -d --build, wait for /api/health, open the
#                browser at the bind-token bootstrap URL so the cookie
#                is set without any copy/paste
#   make down    docker compose down
#   make logs    follow container logs
#   make token   print the current bind token (read from /data/.bind_token)
#   make open    re-open the bootstrap URL (when the cookie was cleared
#                or you're on a different browser)
#
# `make up` reuses the persisted token under ./data/.bind_token, so the
# token stays stable across restarts. Set EVALBOX_WEB_BIND_TOKEN in .env
# to override and pin a token of your choice.

SHELL := /bin/sh
SERVICE := evalbox
CONTAINER := llm-evalbox
PORT := 8765
HEALTH_URL := http://127.0.0.1:$(PORT)/api/health

UNAME := $(shell uname -s)
ifeq ($(UNAME),Darwin)
    OPEN := open
else ifeq ($(UNAME),Linux)
    OPEN := xdg-open
else
    OPEN := echo "open this URL:"
endif

.PHONY: up down logs token open restart build rebuild ps

up:
	docker compose up -d --build
	@printf 'evalbox: waiting for healthcheck...\n'
	@for i in $$(seq 1 30); do \
		if curl -fsS $(HEALTH_URL) >/dev/null 2>&1; then \
			printf 'evalbox: healthy\n'; \
			break; \
		fi; \
		sleep 1; \
	done
	@$(MAKE) --no-print-directory open

open:
	@token="$$(docker exec $(CONTAINER) cat /data/.bind_token 2>/dev/null)"; \
	if [ -z "$$token" ]; then \
		printf 'evalbox: no /data/.bind_token (loopback bind, env-supplied token, or container not ready)\n'; \
		printf 'evalbox: try `make logs` and grep bind-token=\n'; \
		exit 0; \
	fi; \
	url="http://127.0.0.1:$(PORT)/?evalbox_token=$$token"; \
	printf 'evalbox: opening %s\n' "$$url"; \
	$(OPEN) "$$url"

down:
	docker compose down

logs:
	docker compose logs -f $(SERVICE)

token:
	@docker exec $(CONTAINER) cat /data/.bind_token 2>/dev/null \
		|| (printf 'evalbox: no token file — see `make logs`\n' && exit 1)
	@printf '\n'

restart:
	docker compose restart $(SERVICE)

build:
	docker compose build

rebuild:
	docker compose build --no-cache

ps:
	docker compose ps
