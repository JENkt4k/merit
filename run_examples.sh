#!/usr/bin/env sh
set -eu
for source in examples/simple/*.mrt; do
  echo "== $source =="
  merit verify "$source"
done
