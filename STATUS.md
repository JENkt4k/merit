# Merit Status

Status date: 2026-08-04

## Release target

The active target is `v0.1.0-alpha.1`. It is not yet released or complete.

The Python-hosted compiler and C11 backend currently pass 339 local tests and eight interpreter/native acceptance verifiers, including the ledger application. The full command is `./scripts/test.sh`. `VERIFIED_BASELINE.md` records the exact evidence.

## Completed alpha gates

- Generated C evaluates all sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters are outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented subset.

## Remaining alpha gates

1. Add arbitrary-precision decimal and bounded-number reference testing.
2. Run the final local release gate and reconcile every specification and evidence document.

GitHub Actions and other hosted CI are intentionally not part of this release gate. See `ROADMAP.md` for the conditions that must be met before reconsideration.
