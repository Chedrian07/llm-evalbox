#!/bin/sh
# llm-evalbox container entrypoint.
#
# Responsibilities:
#   - When the user binds 0.0.0.0 (the container default) without
#     supplying a bind-token, generate one and print it on the very
#     first line of stdout so they can grab it from `docker logs`.
#   - Forward to `evalbox <subcommand> <args...>`; default subcommand
#     is `web` (the one you actually want to run in a container).
#
# Why a token at all? `evalbox web` refuses non-loopback binds without
# `--bind-token` (cli.py:659) — the token is checked as the
# `x-evalbox-token` header on protected API calls, so a stray container
# exposed on a host network can't be used as an open relay. Browsers can open
# the printed bootstrap URL once to exchange the token for an HttpOnly cookie.
set -e

# Token gate. Only generate when:
#   - no token already in env, AND
#   - we're binding non-loopback (the only case the gate applies to).
host="${EVALBOX_WEB_HOST:-127.0.0.1}"
case "$host" in
    127.0.0.1|::1|localhost) ;;
    *)
        token="$EVALBOX_WEB_BIND_TOKEN"
        if [ -z "$EVALBOX_WEB_BIND_TOKEN" ]; then
            # `od -An -tx1 -N16 /dev/urandom` would also work but tr is
            # ubiquitous on slim images and produces a more compact form.
            token="$(tr -dc 'a-f0-9' < /dev/urandom | head -c 32)"
            export EVALBOX_WEB_BIND_TOKEN="$token"
            printf 'evalbox: bind-token=%s\n' "$token"
        fi
        printf 'evalbox: include this as x-evalbox-token header on protected /api/* calls.\n'
        printf 'evalbox: browser-bootstrap=http://127.0.0.1:%s/?evalbox_token=%s\n' "${EVALBOX_WEB_PORT:-8765}" "$token"
        ;;
esac

# Default subcommand. `evalbox web` is what 99% of container users
# want; `docker run llm-evalbox doctor --base-url ...` still works.
if [ "$#" -eq 0 ]; then
    exec evalbox web
fi

# Allow either `docker run img <subcmd>` or `docker run img evalbox <subcmd>`.
# Without this strip, `docker run img evalbox --help` would invoke
# `evalbox evalbox --help` and typer would complain about an unknown
# command. Friendlier to accept both.
if [ "$1" = "evalbox" ]; then
    shift
fi

exec evalbox "$@"
