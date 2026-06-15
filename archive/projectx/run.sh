#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
S9_CODE_DIR="$SCRIPT_DIR/../S9SharedCode/code"

cd "$S9_CODE_DIR"
exec uv run python "$SCRIPT_DIR/compare_agent.py" "$@"
