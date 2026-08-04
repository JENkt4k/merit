# Merit `v0.1.0-alpha.1` Readiness

Assessment date: 2026-08-04

## Status

Merit has a credible systems-core alpha candidate, but it is not yet ready to be declared complete. The checked subset has strong interpreter/native equivalence, ownership, exact numerics, generic collections, capability auditing, diagnostics, C interoperability, portable left-to-right expression evaluation, unique semantic binding identities, and an enforced ephemeral-only borrow boundary. Remaining release work is documentation consolidation, the ledger acceptance application, and arbitrary-precision numeric reference coverage.

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
| Portable expression sequencing | Recursive C lowering emits ordered temporaries for calls, builtins, constructors, binary operands, conditions, returns, contracts, and vector operations; MIR declares the order | Proven by parity matrix and generated-C inspection |
| Unique binding identity | Parameters, locals, match payloads, references, ownership effects, cleanup, HIR/MIR, interpreter frames, and generated C use deterministic binding IDs | Proven by owned-shadowing parity and compile-fail scope tests |
| Alpha borrow boundary | Returned borrows are limited to field access/mutation, compatible borrow arguments, and validated relays; all storage/value escapes are rejected | Proven by positive and compile-fail boundary matrix; policy is explicit in HIR/MIR |

The current verified baseline is recorded in `VERIFIED_BASELINE.md`.

## Remaining alpha release gates

1. Consolidate roadmap, status, limitations, and changelog documentation.
2. Complete the multi-module exact-decimal ledger acceptance application and ABI verification.
3. Strengthen decimal and bounded numeric coverage against an arbitrary-precision reference.

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

1. Consolidate release documentation.
2. Complete the ledger and numeric-reference gates.
3. Re-run the full gate, every project verifier, shared-library foreign-caller tests, and structured diagnostic suites before declaring alpha.
