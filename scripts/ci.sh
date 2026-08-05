#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repository_root"

printf '%s\n' '== Merit clean-environment gate =='
printf 'repository: %s\n' "$repository_root"
printf 'python: '
python --version
printf 'pip: '
python -m pip --version

if command -v cc >/dev/null 2>&1; then
    printf 'c compiler: '
    cc --version | head -n 1
else
    printf '%s\n' 'error: no C compiler found as cc' >&2
    exit 2
fi

python -m pip check
bash scripts/test.sh
