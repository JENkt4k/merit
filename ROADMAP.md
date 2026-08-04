# Merit Roadmap

## `v0.1.0-alpha.1` release gate

The first alpha closes a deterministic, resource-safe component-language subset. Work proceeds in this order:

1. Universal left-to-right ordered expression lowering — complete.
2. Unique semantic binding IDs for ownership and cleanup — complete.
3. Ephemeral-only returned-borrow boundary — complete.
4. Release-document consolidation — complete when `STATUS.md`, `LIMITATIONS.md`, the specifications, and changelog agree.
5. Multi-module exact-decimal ledger acceptance application with typed errors, explicit allocation, filesystem capabilities, stable exports, and foreign ABI verification — pending.
6. Arbitrary-precision reference coverage for decimal and bounded arithmetic — pending.
7. Final complete local test, project, generated-C, ABI, and specification audit — pending.

The alpha does not require stored references, lifetime parameters, async, concurrency, networking, LLVM, trait objects, specialization, tensors, a package registry, or hosted CI.

## Proven foundation

- Epoch I established exact numerics, bounded values, contracts, capabilities, stable layouts, interpretation, native C generation, and differential testing.
- Epoch II established projects/modules, visibility, enums, typed propagation, strings, owned buffers, explicit allocation, filesystem reads, and CFG-shaped MIR.
- Epoch III established explicit generics and coherent traits, generic collections, typed filesystem errors, allocator identity, destructors, stable shared libraries, structured diagnostics, qualified imports, object caching, ordered expression lowering, binding IDs, and validated ephemeral borrowed returns.

## After the first alpha

Prioritize a non-Python replacement compiler, typed AST/HIR/MIR stability across additional feature sets, deterministic local release tooling, and multiple post-bootstrap releases. Per-module C objects and dependency-granular caching may proceed when they preserve the existing semantic pipeline.

Reconsider persistent hosted CI only after normal production compilation no longer depends on Python, the typed interfaces have survived several feature sets and releases, and local release/acceptance gates are mature and reproducible.

Async, concurrency, networking, LLVM, richer trait machinery, scientific arrays/tensors, registry/package infrastructure, formatter/LSP work, and broad platform automation remain post-alpha roadmap topics. They must not displace semantic correctness or bootstrap replacement.
