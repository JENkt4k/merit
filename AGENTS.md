# Codex Working Agreement — Merit

## Mission
Continue Merit as a deterministic systems language. Preserve exact numerics, explicit allocation, ownership, contracts, capability-gated hazardous operations, stable C interoperability, and interpreter/native semantic equivalence.

## Start here
1. Read `CODEX_HANDOFF.md`, `STATUS.md`, `ROADMAP.md`, and `BOOTSTRAP_STATUS.md`.
2. Read `ARCHITECTURE.md`, `EPOCH-III.md`, and the files under `spec/` as relevant to the milestone.
3. Re-anchor on current `main`: verify the previous PR merged, verify its authoritative gate, and inspect open PRs/branches for overlapping work.
4. Run the relevant baseline/gate before claiming a milestone complete.

## Non-negotiable invariants
- Every accepted program must have matching interpreter and native C behavior for the surface under comparison.
- Side-effecting expressions must be evaluated exactly once in generated C.
- Owned values cannot be copied implicitly.
- Moves, explicit drops, implicit drops, and early returns must never double-destroy resources.
- Allocation and other hazardous operations require the appropriate capability.
- Decimal arithmetic remains exact and its rounding policy explicit.
- Stable-layout declarations must preserve deterministic layout and generated C assertions.
- Preserve one semantic pipeline; do not create a second independent meaning for Merit programs.
- Replacement work must fail closed when a construct is not represented faithfully; never silently fall back to Python in replacement mode.
- Python may remain an independent oracle and temporary orchestration layer, but the `alpha.2` objective is to remove Python semantic authority from normal production compilation.

## Development loop
1. Re-anchor on `main` and verify the previous merge/gate.
2. Choose exactly one highest-value coherent critical-path milestone.
3. Create one branch; do not start parallel autonomous branches.
4. Implement a complete vertical slice with positive, negative/fail-closed, differential, native, and deterministic-artifact tests as applicable.
5. Open or repair exactly one PR.
6. Treat the GitHub Local Gate as authoritative and repair failures on that same PR until green.
7. Stop for manual merge review. Never auto-merge.
8. Do not begin the next milestone until the previous PR is confirmed on `main`.

## Commands
```bash
./scripts/bootstrap.sh
./scripts/test.sh
bash scripts/ci.sh
```

## Current checkpoint
The **`v0.1.0-alpha.1` local release gate is complete**. The active target is **`v0.1.0-alpha.2`**, eliminating Python from the normal compiler path while retaining it as an independent reference oracle.

Keep reference, replacement/bootstrap, trusted, and self-hosted stages distinct. The conceptual compiler pipeline remains:

```text
Source -> Lexer -> Tokens -> CST/AST -> typed semantic/HIR -> ownership/contracts/capabilities -> MIR -> deterministic C -> native compilation
```

The implementation has progressed beyond isolated parser-stage sequencing. Native source-backed function records now reach ownership/control/capability-aware resolved snapshots, multi-function bundles, canonical replacement MIR, deterministic C, and project replacement builds for the supported subset. `prepare-replacement` now exposes a first-class `NativeReplacementDriver` executable boundary.

The immediate critical path is to attach the concrete Merit-native source-unit frontend executable behind that driver boundary and prove source -> native bundle -> prepared artifacts -> replacement MIR -> deterministic C -> executable end to end. Then expand that vertical path across the accepted alpha corpus. Do not broaden the language during bootstrap.
