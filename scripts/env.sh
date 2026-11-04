#!/bin/bash
# Shared helper: read KEY=value from the repo-root .env without sourcing it (bcrypt hashes contain '$').
# Usage: source "$SCRIPT_DIR/env.sh"; value="$(env_value KEY)". Expects WORKSPACE_PATH to be set.

env_value() {
    local line
    line="$(grep -E "^$1=" "$WORKSPACE_PATH/.env" 2>/dev/null | tail -n 1 || true)"
    line="${line#*=}"
    line="${line%\"}"
    line="${line#\"}"
    line="${line%\'}"
    line="${line#\'}"
    printf '%s' "$line"
}
