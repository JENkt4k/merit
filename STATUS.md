# Merit Status

Status date: 2026-11-01

## Release target

The `v0.1.0-alpha.1` local release gate is complete.

**Alpha.2 is released** as `v0.1.0-alpha.2`; package metadata uses the PEP 440
equivalent `0.1.0a2`. Normal project compilation uses the
Merit-native replacement compiler. Python remains the independent semantic and
diagnostic reference oracle.

Pull requests run the short gate on Ubuntu and native Windows; long canonical
gates are deliberate milestone validation. M1-M10 are closed.
`ALPHA2_CLOSURE.md` is the historical detailed release ledger;
`POST_ALPHA2_CLEANUP.md` is the completed cleanup ledger.

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

Those native-resolved artifacts feed the production replacement build boundary.
The Merit-native compiler now materializes canonical MIR and emits deterministic
C and public headers in versioned v4 project artifacts. The host transports and
validates the artifacts, invokes the external C toolchain, and refuses Python
semantic/backend fallback. Project artifacts are source-digest checked so stale
artifacts fail closed. The Python MIR/C implementations remain independent
comparison oracles.

M1-M5 close the documented Alpha.1 semantic and project surfaces through the concrete replacement pipeline. M6 adds a canonical same-source accepted/rejected convergence corpus: accepted cases compare reference and replacement native behavior and deterministic replacement artifacts; rejected cases require both boundaries to reject deterministically. The dedicated corpus gate and ordinary hosted full gates were green before M6 merged.

The proven vertical shape is now:

```text
Merit project/source
  -> concrete Merit-native replacement driver
  -> native project/function/declaration resolution
  -> Merit-owned canonical replacement MIR
  -> Merit-owned deterministic C and public header
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
The bounded post-Alpha.2 cleanup campaign is closed through PR #126. SH3
Merit-owned canonical MIR/backend closed in PR #132. SH4's normal public
compiler-build cutover closed in PR #133: the installed `merit-project build`
command built a usable stage 1 with stage 0 and a usable stage 2 with stage 1
from isolated 46-module source trees. Its final-tree native-Windows full gate
passed (1,712 main tests, 11 M7 tests, 10/10 acceptance projects), and both
hosted short PR checks passed. SH5 stage equivalence and its versioned
self-hosting report are not yet complete; `SELF_HOSTING.md` remains the active
work queue. Alpha.3 resource-model work is out of scope.

## Documentation

A user-facing programming manual lives under `docs/manual/`. It is distinct from bootstrap/compiler-status documentation and should track stable public semantics. Significant examples should remain executable or point to repository examples already covered by the gate so documentation drift is detectable.

## Trust boundary

Python remains the independent semantic and diagnostic reference oracle; it is
not production semantic authority. The Merit-native replacement compiler has
satisfied the Alpha.2 trust criteria and now builds next-stage compilers through
the normal public interface. The complete SH5 equivalence contract and SH6
cross-platform qualification are still required before claiming the
self-hosting campaign is complete.

Do not describe isolated parser/HIR/MIR corpus counts as whole-language replacement percentages. The useful progress metric is vertical removal of Python semantic authority from real production compilation boundaries.
