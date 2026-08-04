# Merit Roadmap

## `v0.1.0-alpha.1` release gate

The first alpha closes a deterministic, resource-safe component-language subset. Work proceeds in this order:

1. Universal left-to-right ordered expression lowering — complete.
2. Unique semantic binding IDs for ownership and cleanup — complete.
3. Ephemeral-only returned-borrow boundary — complete.
4. Release-document consolidation — complete.
5. Multi-module exact-decimal ledger acceptance application with typed errors, explicit allocation, filesystem capabilities, stable exports, and foreign ABI verification — complete.
6. Arbitrary-precision reference coverage for decimal and bounded arithmetic — complete.
7. Final complete local test, project, generated-C, ABI, and specification audit — complete.

The alpha does not require stored references, lifetime parameters, async, concurrency, networking, LLVM, trait objects, specialization, tensors, a package registry, or hosted CI.

## Proven foundation

- Epoch I established exact numerics, bounded values, contracts, capabilities, stable layouts, interpretation, native C generation, and differential testing.
- Epoch II established projects/modules, visibility, enums, typed propagation, strings, owned buffers, explicit allocation, filesystem reads, and CFG-shaped MIR.
- Epoch III established explicit generics and coherent traits, generic collections, typed filesystem errors, allocator identity, destructors, stable shared libraries, structured diagnostics, qualified imports, object caching, ordered expression lowering, binding IDs, and validated ephemeral borrowed returns.

## After the first alpha

Prioritize a non-Python replacement compiler, typed AST/HIR/MIR stability across additional feature sets, deterministic local release tooling, and multiple post-bootstrap releases. Per-module C objects and dependency-granular caching may proceed when they preserve the existing semantic pipeline.

### Active `v0.1.0-alpha.2` bootstrap targets

1. Merit-native source model and lexer with byte-stable spans — complete.
2. Complete accepted-token coverage and differential lexer corpus — complete.
3. Merit-native parser for the bootstrap subset with typed syntax records — in progress; the top-level declaration index is complete.
4. Versioned typed HIR/checker boundary with Python-reference comparison — pending.
5. MIR and deterministic C emission with stage-0/stage-1 equivalence — pending.
6. Accepted-alpha corpus compilation without Python in the normal path — pending.
7. Deterministic local release tooling and multiple post-bootstrap releases — pending.

Reconsider persistent hosted CI only after normal production compilation no longer depends on Python, the typed interfaces have survived several feature sets and releases, and local release/acceptance gates are mature and reproducible.

Async, concurrency, networking, LLVM, richer trait machinery, scientific arrays/tensors, registry/package infrastructure, formatter/LSP work, and broad platform automation remain post-alpha roadmap topics. They must not displace semantic correctness or bootstrap replacement.
