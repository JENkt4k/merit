# Merit Alpha Readiness

Assessment date: 2026-08-03

## Status

Merit has a credible systems-core alpha candidate, but it is not yet ready to be declared a general-purpose language alpha. The checked subset has strong interpreter/native equivalence, ownership, exact numerics, generic collections, capability auditing, diagnostics, and C interoperability. The principal semantic blocker is complete portable sequencing of nested side-effecting expressions in generated C. Stored references and lifetime parameters also require an explicit alpha scope decision.

## Proven gates

| Gate | Evidence | Status |
|---|---|---|
| Interpreter/native equivalence | `scripts/test.sh` runs the full pytest suite and seven project verifiers | Proven for covered programs |
| Exact numerics | Checked primitive/bounded/decimal helpers, trap-aware MIR folding, `spec/NUMERICS.md` | Proven for implemented numeric types |
| Ownership and deterministic destruction | Shared `TypeTable`/`OwnershipEffects`, custom-destructor parity, owned parameter/temporary/`try`/match tests | Proven for accepted ownership forms |
| Generic traits and collections | User trait coherence, project-wide monomorphization, allocator-retaining and nested `Vec<T>`, trait/collection acceptance projects | Proven within documented trait limits |
| Capability policy | Allocation and filesystem hazards are lexically checked and audited; filesystem acceptance verifies both runtimes | Proven for implemented hazards |
| Borrowed views | Ephemeral shared/mutable returns, const-correct C pointers, postconditions, project and shared-library tests | Proven for ephemeral borrows |
| C interoperability | Stable-layout assertions, public type-closure checks, shared builds and foreign-caller tests | Proven for implemented stable ABI surface |
| Project diagnostics | Embedded primary/related provenance, generic source maps, cross-module remapping, text/JSON diagnostics | Proven by source/project diagnostic suites |
| Typed semantic pipeline | Immutable per-kind nodes, typed declarations/parameters/parser intermediates, explicit HIR/MIR serialization, no external node-span maps | Proven by implementation search and semantic metadata tests |
| Build repeatability | Deterministic project loading and content-addressed merged-translation-unit object cache | Proven; not yet per-module compilation |

The current verified baseline is recorded in `VERIFIED_BASELINE.md`.

## Alpha blockers

1. **Portable expression sequencing.** Assignment, replacement, printing, owned vector replacement, and zero-copy transfer have explicit temporaries. General nested calls, builtin arguments, constructors, and binary operands can still rely on C argument evaluation order. Complete this with one recursive expression-lowering path that emits ordered prelude temporaries for both native C and inspection metadata.
2. **Stored-reference scope decision.** Ephemeral returned borrows are safe and tested. Either add reference-typed local storage with explicit lifetime relationships or declare stored references outside the first alpha and retain compile-time rejection.
3. **Unique binding identity.** Ownership state is keyed by source name, so shadowing is conservatively rejected. Introduce semantic binding IDs before enabling shadowing or implicit cleanup for arbitrary nested lexical scopes.

## Accepted alpha limitations

- Owned match payloads and owned locals introduced inside branch/loop/arm scopes require explicit move or drop before scope exit.
- Owned `old(...)` snapshots are rejected; only Copy snapshots are supported.
- Partial moves from owned aggregate fields and subobject-disjoint borrowing are unavailable.
- Destructor bodies cannot change ownership or enter capability regions.
- Generic arguments are explicit; associated types, blanket impls, specialization, trait objects, dynamic dispatch, and higher-kinded types are absent.
- Trait method signatures cannot declare effects or required capabilities.
- System and portable allocators have distinct identities but currently share host allocation primitives.

## Post-alpha engineering

- Per-module C objects and dependency-granular cache invalidation
- Typed generic IR instead of source-rewrite monomorphization
- Broader optimizer work and a production LLVM backend
- Package registry, formatter, language server, concurrency, and production tooling

## Recommended execution order

1. Implement recursive ordered expression lowering and add side-effect-order parity matrices.
2. Decide and document the first-alpha stored-reference boundary.
3. Introduce unique binding identities, then relax conservative shadowing/scope restrictions.
4. Re-run the full gate, every project verifier, shared-library foreign-caller tests, and structured diagnostic suites before declaring alpha.
