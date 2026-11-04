#!/bin/bash

set -e # Exit immediately if a command exits with a non-zero status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_PATH="$(dirname "$SCRIPT_DIR")"
pushd "$WORKSPACE_PATH" >/dev/null || exit 1

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Install the dongseon dev environment (backend + frontend)"
    echo
    echo "Options:"
    echo "  -p, --python_ver PYTHON_VERSION     Specify Python version"
    echo "                                       (default: 3.12)"
    echo "      --skip_frontend                 Skip pnpm install"
    echo "  -h, --help                          Show this help message"
    echo
    echo "Examples:"
    echo "  $0                                  # Install with Python 3.12"
    echo "  $0 --python_ver 3.13                # Install with Python 3.13"
}

# Default values
PYTHON_VERSION="3.12"
SKIP_FRONTEND=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--python_ver)
            PYTHON_VERSION="$2"
            shift 2
            ;;
        --skip_frontend)
            SKIP_FRONTEND=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate Python version
if [[ "$PYTHON_VERSION" != "3.12" && "$PYTHON_VERSION" != "3.13" ]]; then
    echo "Error: Python version must be either '3.12' or '3.13'"
    show_help
    exit 1
fi

echo "PYTHON_VERSION: $PYTHON_VERSION"

if ! command -v uv &>/dev/null; then
    echo "Error: uv is not installed. See https://docs.astral.sh/uv/"
    exit 1
fi

# Backend: sync dependencies and register pre-commit hooks
uv sync --python "$PYTHON_VERSION"
uv run --no-sync pre-commit install || true

# Use the repo commit message template
git config commit.template .gitmessage.txt || true

# Frontend
if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
    if ! command -v pnpm &>/dev/null; then
        echo "Error: pnpm is not installed. Run: npm install -g pnpm"
        exit 1
    fi
    pnpm --dir frontend install
fi

# Local config files (never overwrite existing ones)
[[ -f .env ]] || cp .env.example .env
[[ -f config/profile.yaml ]] || cp config/profile.example.yaml config/profile.yaml

popd >/dev/null
