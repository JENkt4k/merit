# Merit Roadmap

## `v0.1.0-alpha.1` release gate

The first alpha closed a deterministic, resource-safe component-language subset. Its ordered gates are complete: portable left-to-right expression lowering, unique semantic binding IDs, the ephemeral returned-borrow boundary, release-document consolidation, the multi-module exact-decimal ledger acceptance application, arbitrary-precision numeric reference coverage, and the final local/specification audit.

The alpha deliberately excludes stored references, lifetime parameters, async, concurrency, networking, LLVM, trait objects, specialization, tensors, and package-registry work.

## Proven foundation

- Epoch I established exact numerics, bounded values, contracts, capabilities, stable layouts, interpretation, native C generation, and differential testing.
- Epoch II established projects/modules, visibility, enums, typed propagation, strings, owned buffers, explicit allocation, filesystem reads, and CFG-shaped MIR.
- Epoch III established explicit generics and coherent traits, generic collections, typed filesystem errors, allocator identity, destructors, stable shared libraries, structured diagnostics, qualified imports, object caching, ordered expression lowering, binding IDs, and validated ephemeral borrowed returns.

## Active `v0.1.0-alpha.2` replacement compiler

The objective is unchanged: eliminate Python semantic authority from normal production compilation while retaining the Python compiler as an independent oracle until the replacement qualifies as trusted. Do not broaden the language to achieve bootstrap.

Early bootstrap work established deterministic native lexer/parser records and canonical expression AST/HIR/MIR contracts. Development has since moved vertically through real source-backed functions rather than waiting for every isolated stage fixture to reach whole-language coverage first.

### Completed replacement boundaries

1. Merit-native lexer and source-oriented statement/clause/expression discovery for the measured bootstrap corpus.
2. Canonical expression AST/HIR/MIR contracts with differential Python-oracle and interpreter/native evidence for their measured cases.
3. Source-backed function records carrying body instructions and source provenance.
4. Function contracts and contract-local metadata in the native path.
5. Whole-function assembly records and deterministic instruction-source identity.
6. Ownership bindings/effects and path-sensitive control-flow integration for supported source functions.
7. CFG records and deterministic placement integrated with resolved source functions.
8. Capability identities/effects carried through the resolved source-function boundary.
9. Versioned resolved-source-function snapshots and multi-function `resolved-source-function-bundle-v1` framing.
10. Canonical replacement MIR reconstruction and deterministic C/native execution from native-resolved artifacts.
11. Production project replacement mode that consumes prepared native artifacts and refuses Python fallback.
12. Source-digest validation and atomic preparation/publication of replacement artifacts.
13. A first-class `NativeReplacementDriver` executable boundary replacing the arbitrary producer-command seam.

### Immediate critical path

1. Attach a concrete Merit-native source-unit frontend executable behind `NativeReplacementDriver`.
2. Prove source unit -> multi-function native bundle -> prepared artifacts -> canonical replacement MIR -> deterministic C -> executable end to end.
3. Expand that vertical path across remaining accepted-alpha statements, control flow, ownership/resources, contracts, capabilities, exact numerics, aggregates, generics/traits, and module interactions.
4. Maintain accepted/rejected differential corpus parity and fail closed whenever the replacement compiler cannot represent a construct faithfully.
5. Move the acceptance applications through the replacement path until the documented alpha surface compiles without Python semantic lowering.
6. Make replacement compilation the normal production path only after its semantic coverage and parity gates justify the transition.
7. Establish stage-0/stage-1 equivalence and reproducibility.
8. Begin self-hosting only after the replacement compiler qualifies as trusted.

### Trust criteria

Trust is based on deterministic typed contracts, accepted/rejected corpus parity, interpreter/native agreement, stable artifact framing, compile-pass/fail coverage, acceptance behavior, and reproducible stages. Counts for isolated parser or expression fixtures are evidence for those boundaries, not a whole-language replacement percentage.

Async, concurrency, networking, LLVM, richer trait machinery, scientific arrays/tensors, registry/package infrastructure, formatter/LSP work, and broad platform automation remain post-alpha roadmap topics. They must not displace semantic correctness or replacement of the normal compiler path.
