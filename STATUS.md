# Merit Status

Status date: 2026-09-02

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

Development is on `v0.1.0-alpha.2`: remove Python from the normal compiler path without broadening the language. Python remains an independent semantic/diagnostic oracle until the replacement compiler qualifies as trusted.

The canonical GitHub gates run the full clean suite on Ubuntu and native Windows. PR #109 is merged. `ALPHA2_CLOSURE.md` is the authoritative source for detailed replacement-coverage and milestone state.

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

The concrete Merit-native driver now carries the Alpha.1 statement/control-flow, resource/payload-enum lifecycle, exact-numeric/aggregate, and generic/trait surfaces through the established replacement pipeline. Those four closure milestones (M1-M4) are closed with the evidence recorded in `ALPHA2_CLOSURE.md`.

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

M5 project/module/import/export/visibility closure is the current frontier. M6 corpus convergence, M7 acceptance migration, M8 production-path cutover, M9 reproducibility/trust, and M10 release audit remain later milestones. Alpha.2 is therefore neither complete nor trusted.

## Documentation

A user-facing programming manual now lives under `docs/manual/`. It is distinct from bootstrap/compiler-status documentation and should track stable public semantics. Significant examples should remain executable or point to repository examples already covered by the gate so documentation drift is detectable.

## Trust boundary

Python remains the independent semantic and diagnostic reference oracle. The Merit-native replacement compiler is not yet trusted or self-hosted. Trust requires complete accepted/rejected corpus parity for the target alpha surface, stable typed stage contracts, deterministic stage agreement, and a clean release cycle. Self-hosting begins only after that trust gate and requires reproducible stage equivalence.

Do not describe isolated parser/HIR/MIR corpus counts as whole-language replacement percentages. The useful progress metric is vertical removal of Python semantic authority from real production compilation boundaries.
