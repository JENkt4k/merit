#!/usr/bin/env bash
set -euo pipefail

repository_root="$(pwd -P)"
pytest_log="$(mktemp)"
filesystem_test_directory="$(mktemp -d)"
ledger_test_directory="$(mktemp -d)"
trap 'rm -f "$pytest_log"; rm -rf "$filesystem_test_directory" "$ledger_test_directory"' EXIT

start_group() {
    local name="$1"
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
        printf '::group::%s\n' "$name"
    else
        printf '\n== %s ==\n' "$name"
    fi
}

end_group() {
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
        printf '::endgroup::\n'
    fi
}

run_project() {
    local name="$1"
    local path="$2"
    start_group "acceptance: $name"
    merit-project verify "$path"
    end_group
}

start_group "pytest"
python -m pytest -q | tee "$pytest_log"
end_group
pytest_summary="$(tail -n 1 "$pytest_log")"

run_project "text_pipeline" "examples/projects/text_pipeline"
run_project "binary_packet" "examples/projects/binary_packet"
run_project "generic_result" "examples/projects/generic_result"
run_project "trait_bounds" "examples/projects/trait_bounds"
run_project "generic_collections" "examples/projects/generic_collections"
run_project "borrowed_views" "examples/projects/borrowed_views"
run_project "bootstrap_lexer" "examples/projects/bootstrap_lexer"

start_group "acceptance: filesystem_capabilities"
(
    cd "$filesystem_test_directory"
    merit-project verify "$repository_root/examples/projects/filesystem_capabilities" -o "$filesystem_test_directory/filesystem_capabilities"
)
end_group

start_group "acceptance: ledger_app"
(
    cd "$ledger_test_directory"
    merit-project verify "$repository_root/examples/projects/ledger_app" -o "$ledger_test_directory/ledger_app"
)
end_group

printf '\nMerit local gate passed: %s; 9/9 acceptance projects verified.\n' "$pytest_summary"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    cat >>"$GITHUB_STEP_SUMMARY" <<EOF
## Merit local gate

- **Pytest:** $pytest_summary
- **Acceptance projects:** 9 / 9 verified
- **Interpreter/native agreement:** passed for every acceptance project
- **Bootstrap corpus contract:** manifest and canonical AST tests included in pytest
EOF
fi
