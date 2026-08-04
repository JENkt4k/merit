# Merit Status

Status date: 2026-08-04

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

The reference compiler, C11 backend, and bootstrap fixtures currently pass 363 local tests and nine interpreter/native acceptance verifiers, including the ledger application and Merit-native compiler fixture. The full command is `./scripts/test.sh`. `VERIFIED_BASELINE.md` records the exact evidence and `BOOTSTRAP_STATUS.md` records compiler-quality metrics.

## Completed alpha gates

- Generated C evaluates all sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters are outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented subset.
- The arbitrary-precision decimal and unbounded-integer references validate every rounding policy and bounded arithmetic boundaries in both runtimes.

## Release-gate result

All seven ordered alpha gates are complete. No known semantic correctness blocker remains undocumented; deliberate exclusions are recorded in `LIMITATIONS.md`.

GitHub Actions and other hosted CI are intentionally not part of this release gate. See `ROADMAP.md` for the conditions that must be met before reconsideration.

## Active post-alpha development

The next target is `v0.1.0-alpha.2`, focused on replacing the Python-hosted normal compilation path. Typed expression trees now preserve atoms/groups, calls, arguments, fields, direct constructors, single-type generic calls, arithmetic, and comparisons against an independent oracle. Qualified and multi-type constructors, malformed-expression recovery, and typed statement/clause operands remain before the parser gate can close. Unrelated language expansion and hosted CI remain deferred.

Python remains the semantic and diagnostic reference oracle. The Merit implementation is a bootstrap compiler only; it is neither trusted nor self-hosted. Trust requires complete accepted/rejected corpus parity, stable AST/HIR/MIR contracts, deterministic stage agreement, and a clean release cycle. Self-hosting begins only after trust and requires reproducible stage-1/stage-2 equivalence.
