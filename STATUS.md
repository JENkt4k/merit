# Merit Status

Status date: 2026-09-03

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

Development is on `v0.1.0-alpha.2`: remove Python from the normal compiler path without broadening the language. Python remains an independent semantic/diagnostic oracle until the replacement compiler qualifies as trusted.

The canonical GitHub gates run the full clean suite on Ubuntu and native Windows. Alpha.2 milestones M1-M6 are closed. `ALPHA2_CLOSURE.md` is the authoritative source for detailed replacement-coverage and milestone state.

## Proven alpha foundation

- Generated C evaluates sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters remain outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented alpha subset.
- The exact-decimal ledger application exercises multi-module typed errors, filesystem capabilities, explicit allocation, stable exports, and foreign ABI verification.
- Independent arbitrary-precision references cover decimal rounding policies and bounded arithmetic boundaries.

All seven ordered `v0.1.0-alpha.1` gates remain complete. No known semantic correctness blocker remains undocumented; deliberate exclusions remain recorded in `LIMITATIONS.md`.

## Active replacement-compiler state

The replacement effort has progressed beyond the early isolated lexer/parser/AST/HIR/MIR checkpoints. Native source-backed resolution carries function bodies, contracts, instruction provenance, ownership bindings/effects, CFG records/placement, capability identities, project/module identity, generics/traits, exact numerics, aggregates, resources, and stable export metadata into the production replacement boundary.

Those native-resolved artifacts feed the production replacement build boundary. Replacement builds consume prepared snapshots/project artifacts, reconstruct canonical replacement MIR, emit deterministic C, compile it, and refuse to fall back to the Python reference compiler. Project artifacts are source-digest checked so stale snapshots fail closed.

M1-M5 close the documented Alpha.1 semantic and project surfaces through the concrete replacement pipeline. M6 adds a canonical same-source accepted/rejected convergence corpus: accepted cases compare reference and replacement native behavior and deterministic replacement artifacts; rejected cases require both boundaries to reject deterministically. The dedicated corpus gate and ordinary hosted full gates were green before M6 merged.

The proven vertical shape is now:

```text
Merit project/source
  -> concrete Merit-native replacement driver
  -> native project/function/declaration resolution
  -> resolved replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
```

Python remains orchestration/transport at current seams and the independent oracle; it is not permitted to silently supply target-source semantic lowering to replacement mode.

## Current frontier

M7 acceptance migration is the current frontier. It must drive all 10 canonical acceptance projects through replacement compilation and native execution with no Python semantic fallback; the exact-decimal `ledger_app` is mandatory evidence. The implementation/closure contract is recorded in `docs/M7_ACCEPTANCE_MIGRATION.md`.

M8 production-path cutover, M9 reproducibility/trust, and M10 release audit follow. Alpha.2 is therefore not yet complete or trusted.

## Documentation

A user-facing programming manual lives under `docs/manual/`. It is distinct from bootstrap/compiler-status documentation and should track stable public semantics. Significant examples should remain executable or point to repository examples already covered by the gate so documentation drift is detectable.

## Trust boundary

Python remains the independent semantic and diagnostic reference oracle. The Merit-native replacement compiler is not yet trusted or self-hosted. M6 establishes accepted/rejected semantic corpus convergence, but trust additionally requires real acceptance-application migration, production-path cutover, stable typed stage contracts, deterministic stage agreement, and a clean reproducible release cycle. Self-hosting begins only after that trust gate and requires reproducible stage equivalence.

Do not describe isolated parser/HIR/MIR corpus counts as whole-language replacement percentages. The useful progress metric is vertical removal of Python semantic authority from real production compilation boundaries.