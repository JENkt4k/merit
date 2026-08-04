# Merit Status

Status date: 2026-08-04

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

The Python-hosted compiler and C11 backend currently pass 346 local tests and eight interpreter/native acceptance verifiers, including the ledger application. The full command is `./scripts/test.sh`. `VERIFIED_BASELINE.md` records the exact evidence.

## Completed alpha gates

- Generated C evaluates all sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters are outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented subset.
- The arbitrary-precision decimal and unbounded-integer references validate every rounding policy and bounded arithmetic boundaries in both runtimes.

## Release-gate result

All seven ordered alpha gates are complete. No known semantic correctness blocker remains undocumented; deliberate exclusions are recorded in `LIMITATIONS.md`.

GitHub Actions and other hosted CI are intentionally not part of this release gate. See `ROADMAP.md` for the conditions that must be met before reconsideration.
