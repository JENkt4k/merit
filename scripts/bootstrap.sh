#!/usr/bin/env bash
set -euo pipefail
if command -v python >/dev/null 2>&1; then
    merit_python=python
elif command -v python3 >/dev/null 2>&1; then
    merit_python=python3
else
    echo "Merit bootstrap requires Python 3" >&2
    exit 1
fi
"$merit_python" -m pip install -e ".[dev]" --no-build-isolation
