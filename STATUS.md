# Merit Status

Status date: 2026-08-19

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

Development is on `v0.1.0-alpha.2`: remove Python from the normal compiler path without broadening the language. Python remains an independent semantic/diagnostic oracle until the replacement compiler qualifies as trusted.

The authoritative GitHub Local Gate covers a full clean Ubuntu/Python 3.11/system-C run plus a focused Windows/Python 3.11/MSYS2 UCRT64 GCC native smoke run. PR #79 completed the current multi-function concrete-driver milestone before merge.

## Proven alpha foundation

- Generated C evaluates sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters remain outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented alpha subset.
- The exact-decimal ledger application exercises multi-module typed errors, filesystem capabilities, explicit allocation, stable exports, and foreign ABI verification.
- Independent arbitrary-precision references cover decimal rounding policies and bounded arithmetic boundaries.

All seven ordered `v0.1.0-alpha.1` gates remain complete. No known semantic correctness blocker remains undocumented; deliberate exclusions remain recorded in `LIMITATIONS.md`.

## Active replacement-compiler state

The replacement effort has progressed beyond the early isolated lexer/parser/AST/HIR checkpoints. The repository now contains native source-backed function resolution that carries function bodies, contracts, instruction provenance, ownership bindings/effects, CFG records/placement, and capability identities into versioned resolved-source snapshots. Multiple resolved functions from one source unit are framed in a versioned `resolved-source-function-bundle-v1` bundle.

Those native-resolved artifacts feed the production replacement build boundary. Replacement builds consume prepared snapshots, reconstruct canonical replacement MIR, emit deterministic C, compile it, and refuse to fall back to the Python reference compiler. Project artifacts are source-digest checked so stale snapshots fail closed.

PR #75 established multi-function source-unit bundles. PR #76 established the first-class `NativeReplacementDriver` executable boundary. PR #78 attached the first concrete Merit-native driver for a deliberately narrow single-function/no-enum/no-capability source subset. PR #79 removed the single-function restriction: the concrete native driver now discovers top-level functions from lexed source, slices complete balanced function token views while preserving original source offsets, lowers each independently through the existing resolved-function pipeline, and emits one MRBF item per function.

The complete proven vertical shape is now:

```text
Merit source unit
  -> concrete Merit-native replacement driver
  -> native function discovery/slicing
  -> resolved multi-function bundle
  -> prepared replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
```

Python remains orchestration/transport at this boundary and the independent oracle; it does not perform target-source function slicing or semantic lowering for this proven replacement slice.

## Current frontier

The immediate production frontier is **native source derivation of enum-variant and capability catalogs** for the concrete driver. PR #79 intentionally kept the existing no-enum/no-capability restriction rather than inventing incomplete catalog semantics.

The next coherent implementation milestone should derive those catalogs from the same source/tokens consumed by the native driver, feed them into the existing resolved match/capability pipeline, prove enum/capability source units through driver -> MRBF -> prepared replacement -> canonical MIR -> deterministic native execution, and continue to fail closed for constructs whose semantics are not yet represented.

After that, expand the same vertical path toward the complete accepted alpha corpus: remaining statements/control flow, ownership/resources, contracts, exact numerics, aggregates, generics/traits, and module interactions. Normal project compilation can move to the replacement path only when semantic coverage and accepted/rejected corpus parity justify it.

## Documentation

A user-facing programming manual now lives under `docs/manual/`. It is distinct from bootstrap/compiler-status documentation and should track stable public semantics. Significant examples should remain executable or point to repository examples already covered by the gate so documentation drift is detectable.

## Trust boundary

Python remains the independent semantic and diagnostic reference oracle. The Merit-native replacement compiler is not yet trusted or self-hosted. Trust requires complete accepted/rejected corpus parity for the target alpha surface, stable typed stage contracts, deterministic stage agreement, and a clean release cycle. Self-hosting begins only after that trust gate and requires reproducible stage equivalence.

Do not describe isolated parser/HIR/MIR corpus counts as whole-language replacement percentages. The useful progress metric is vertical removal of Python semantic authority from real production compilation boundaries.
