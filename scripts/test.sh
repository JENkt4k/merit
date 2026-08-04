#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
merit-project verify examples/projects/text_pipeline
merit-project verify examples/projects/binary_packet
merit-project verify examples/projects/generic_result
merit-project verify examples/projects/trait_bounds
merit-project verify examples/projects/generic_collections
merit-project verify examples/projects/borrowed_views
merit-project verify examples/projects/bootstrap_lexer
repository_root="$(pwd -P)"
filesystem_test_directory="$(mktemp -d)"
trap 'rm -rf "$filesystem_test_directory"' EXIT
(
    cd "$filesystem_test_directory"
    merit-project verify "$repository_root/examples/projects/filesystem_capabilities" -o "$filesystem_test_directory/filesystem_capabilities"
)
ledger_test_directory="$(mktemp -d)"
trap 'rm -rf "$filesystem_test_directory" "$ledger_test_directory"' EXIT
(
    cd "$ledger_test_directory"
    merit-project verify "$repository_root/examples/projects/ledger_app" -o "$ledger_test_directory/ledger_app"
)
