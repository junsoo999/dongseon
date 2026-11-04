#!/bin/bash

set -e # Exit immediately if a command exits with a non-zero status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_PATH="$(dirname "$SCRIPT_DIR")"
pushd "$WORKSPACE_PATH" >/dev/null || exit 1

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Run pytest tests for dongseon"
    echo
    echo "Options:"
    echo "  --tests PATH         Test directory or file (default: tests/unit_test)"
    echo "  --coverage           Emit XML coverage and term-missing report"
    echo "  -h, --help           Show this help message"
    echo
    echo "Examples:"
    echo "  $0                   # Run unit tests"
    echo "  $0 --coverage        # Run with coverage reports"
}

# Default values
TESTS="tests/unit_test"
COVERAGE=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tests)
            TESTS="$2"
            shift 2
            ;;
        --coverage)
            COVERAGE=1
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

PYTEST_ARGS=("$TESTS" "--junitxml=pytest-report.xml")

if [[ "$COVERAGE" -eq 1 ]]; then
    PYTEST_ARGS+=(
        "--cov=dongseon"
        "--cov-report=xml:coverage.xml"
        "--cov-report=term-missing"
    )
fi

uv run --no-sync pytest "${PYTEST_ARGS[@]}"

popd >/dev/null
