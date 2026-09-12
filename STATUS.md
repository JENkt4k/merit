# Merit Status

Status date: 2026-09-12

## Release target

The `v0.1.0-alpha.1` local release gate is complete.

**Alpha.2 is released** as `v0.1.0-alpha.2`; package metadata uses the PEP 440
equivalent `0.1.0a2`. Normal project compilation uses the
Merit-native replacement compiler. Python remains the independent semantic and
diagnostic reference oracle.

The canonical GitHub gates run the full clean suite on Ubuntu and native
Windows. M1-M10 are closed. `ALPHA2_CLOSURE.md` is the historical detailed
release ledger; `POST_ALPHA2_CLEANUP.md` is the active work queue.

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

M7 acceptance migration closed in PR #113, M8 production-path cutover closed in
PR #114, and M9 reproducibility/trust closed in PR #115. All ten acceptance
projects pass replacement compilation and native execution. Stage 1 and stage
2 reproduce canonical generated C and public headers byte-for-byte, and all
three native stages agree on the fixed protocol probe in clean Ubuntu and
native-Windows environments.

The replacement compiler is trusted for the documented Alpha.1 production
surface, and Alpha.2 completed M10 and was tagged at merge commit `53699f2`.
The active frontier is the bounded post-Alpha.2 cleanup campaign: first classify
and migrate existing semantic numeric identifiers without renumbering or
semantic changes, then address separately tracked bootstrap/test-infrastructure
defects. Ownership/buffer/tensor expansion belongs to a later Alpha.3 plan.

## Documentation

A user-facing programming manual lives under `docs/manual/`. It is distinct from bootstrap/compiler-status documentation and should track stable public semantics. Significant examples should remain executable or point to repository examples already covered by the gate so documentation drift is detectable.

## Trust boundary

Python remains the independent semantic and diagnostic reference oracle; it is
not production semantic authority. The Merit-native replacement compiler has
satisfied the Alpha.2 trust criteria but is not self-hosted. Self-hosting is a
post-Alpha.2 milestone and must preserve reproducible stage equivalence.

Do not describe isolated parser/HIR/MIR corpus counts as whole-language replacement percentages. The useful progress metric is vertical removal of Python semantic authority from real production compilation boundaries.
