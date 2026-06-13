#!/usr/bin/env bash
# One-click backend startup for Linux/macOS.
# Forwards any flags to auto_start.py, e.g.:  ./scripts/start.sh --prod
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: Python 3 not found. Install it from https://www.python.org/downloads/" >&2
  exit 1
fi

exec "$PY" "$SCRIPT_DIR/auto_start.py" "$@"
