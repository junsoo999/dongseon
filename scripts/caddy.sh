#!/bin/bash

set -e # Exit immediately if a command exits with a non-zero status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_PATH="$(dirname "$SCRIPT_DIR")"
# shellcheck source=scripts/env.sh
source "$SCRIPT_DIR/env.sh"

show_help() {
    echo "Usage: $0 <run|validate|hash>"
    echo "Run Caddy (basic auth, per-app routing) behind the Cloudflare Tunnel for remote access"
    echo
    echo "Reads DONGSEON_DOMAIN, DONGSEON_AUTH_USER, DONGSEON_AUTH_HASH and DONGSEON_PROXY_PORT from .env."
    echo "The Cloudflare tunnel connector is shared (any running cloudflared on this Mac); only its"
    echo "published route for DONGSEON_DOMAIN -> http://localhost:\$DONGSEON_PROXY_PORT belongs to dongseon."
    echo
    echo "Commands:"
    echo "  run        Run Caddy in the foreground (what launchd runs)"
    echo "  validate   Check config/Caddyfile with the values from .env"
    echo "  hash       Prompt for a password and print its bcrypt hash for DONGSEON_AUTH_HASH"
}

CADDY_BIN="${CADDY_BIN:-$(command -v caddy || echo /opt/homebrew/bin/caddy)}"
if [[ ! -x "$CADDY_BIN" ]]; then
    echo "Error: caddy not found. Install it with 'brew install caddy'."
    exit 1
fi


load_env() {
    DONGSEON_DOMAIN="$(env_value DONGSEON_DOMAIN)"
    DONGSEON_AUTH_USER="$(env_value DONGSEON_AUTH_USER)"
    DONGSEON_AUTH_HASH="$(env_value DONGSEON_AUTH_HASH)"
    DONGSEON_PORT="$(env_value DONGSEON_PORT)"
    DONGSEON_PORT="${DONGSEON_PORT:-8100}"
    DONGSEON_PROXY_PORT="$(env_value DONGSEON_PROXY_PORT)"
    DONGSEON_PROXY_PORT="${DONGSEON_PROXY_PORT:-8081}"
    DONGSEON_LOG_DIR="$WORKSPACE_PATH/data/logs"
    for name in DONGSEON_DOMAIN DONGSEON_AUTH_USER DONGSEON_AUTH_HASH; do
        if [[ -z "${!name}" ]]; then
            echo "Error: $name is empty in .env (see .env.example)"
            exit 1
        fi
    done
    if [[ "$DONGSEON_AUTH_HASH" != \$2* ]]; then
        echo "Error: DONGSEON_AUTH_HASH must be a bcrypt hash; run '$0 hash'"
        exit 1
    fi
    mkdir -p "$DONGSEON_LOG_DIR"
    export DONGSEON_DOMAIN DONGSEON_AUTH_USER DONGSEON_AUTH_HASH DONGSEON_PORT DONGSEON_PROXY_PORT DONGSEON_LOG_DIR
}

case "${1:-}" in
    run)
        load_env
        exec "$CADDY_BIN" run --config "$WORKSPACE_PATH/config/Caddyfile" --adapter caddyfile
        ;;
    validate)
        load_env
        "$CADDY_BIN" validate --config "$WORKSPACE_PATH/config/Caddyfile" --adapter caddyfile
        ;;
    hash)
        "$CADDY_BIN" hash-password
        ;;
    -h|--help)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
