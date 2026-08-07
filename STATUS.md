# Merit Status

Status date: 2026-08-07

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

Development is now on `v0.1.0-alpha.2`, whose purpose is to remove Python from the normal compiler path without broadening the language. Python remains the independent semantic/diagnostic oracle until the replacement compiler qualifies as trusted.

The latest fully green hosted clean-environment checkpoint passed **671 tests with 1 skipped test and all 9 acceptance projects** on Ubuntu/Python 3.11/system C, while the focused Windows/Python 3.11/MSYS2 UCRT64 GCC native smoke gate also passed. The current branch adds two further nested-vector visibility regressions and is rerunning that gate.

## Completed alpha gates

- Generated C evaluates all sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters are outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented subset.
- The exact-decimal ledger application remains the substantial multi-module acceptance gate, including typed errors, filesystem capabilities, explicit allocation, stable exports, and foreign ABI verification.
- The arbitrary-precision decimal and unbounded-integer references validate every rounding policy and bounded arithmetic boundaries in both runtimes.

## Release-gate result

All seven ordered `v0.1.0-alpha.1` gates are complete. No known semantic correctness blocker remains undocumented; deliberate exclusions are recorded in `LIMITATIONS.md`.

Hosted CI is now used as a verification aid for the existing local gate, including a focused native Windows smoke job. It does not change the bootstrap trust criteria: stage contracts and local reproducibility remain authoritative.

## Active replacement-compiler development

The Merit-native front end now has a real expression AST boundary after the versioned expression parser records. `bootstrap-expression-v1` records lower into deterministic flat `AstNodeRecord` storage, explicit grouping is removed from semantic meaning while its source provenance is retained, and malformed record streams are rejected deterministically.

For every expression in the current manifest corpus, the Merit interpreter and generated-native implementation agree on the flat AST representation. The flat representation also reconstructs exactly to the Python `bootstrap-ast-v1` canonical tree and stable compact JSON oracle, including nested grouping provenance. This is an expression-stage AST checkpoint, not completion of the whole accepted-alpha AST.

The checkpoint also fixed public project visibility for builtin vectors: public `Vec<T>` surfaces are accepted when `T` is public and remain rejected when the element type is private, including nested vector wrapping.

Parser work remains open for typed statement/clause operands, qualified and multi-type constructors, deterministic malformed-expression recovery, and the explicit trivia-preserving CST boundary. Whole-alpha AST coverage, typed HIR, semantic checking over HIR, deterministic MIR, C-from-MIR, stage equivalence, and Python-free normal compilation remain subsequent gates.

Python remains the semantic and diagnostic reference oracle. The Merit implementation is a bootstrap compiler only; it is neither trusted nor self-hosted. Trust requires complete accepted/rejected corpus parity, stable AST/HIR/MIR contracts, deterministic stage agreement, and a clean release cycle. Self-hosting begins only after trust and requires reproducible stage equivalence.
