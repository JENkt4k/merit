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

1. Complete typed statement syntax records — in progress; statement kinds and deterministic envelopes are complete, typed operands remain.
2. Complete expression precedence and typed expression records — in progress; atoms, grouping, calls, fields, argument lists, arithmetic, and comparisons are implemented, while constructors, generic calls, and full recovery remain.
3. Complete typed effects, capability, precondition, and postcondition operands — pending; clause introducers are indexed.
4. Complete deterministic parser recovery — pending; initial structural recovery and diagnostics are implemented.
5. Establish an explicit trivia-preserving CST-to-AST boundary — pending.
6. Define typed AST records for the accepted alpha language — pending.
7. Lower AST into typed HIR — pending.
8. Differentially compare reference and bootstrap HIR over the accepted corpus — pending.
9. Implement semantic checking over HIR — pending.
10. Implement ownership, contracts, capabilities, and exact numeric rules over HIR — pending.
11. Lower checked HIR into deterministic MIR — pending.
12. Emit C only from MIR — pending.
13. Establish stage-0/stage-1 compiler equivalence — pending.
14. Compile the complete accepted alpha corpus without Python in the normal path — pending.
15. Begin self-hosting only after the bootstrap compiler qualifies as trusted — pending.

The Merit-native lexer and its independent token/span corpus are complete prerequisites. The current syntax index is a parser-development artifact, not yet the CST or AST.

Reconsider persistent hosted CI only after normal production compilation no longer depends on Python, the typed interfaces have survived several feature sets and releases, and local release/acceptance gates are mature and reproducible.

Async, concurrency, networking, LLVM, richer trait machinery, scientific arrays/tensors, registry/package infrastructure, formatter/LSP work, and broad platform automation remain post-alpha roadmap topics. They must not displace semantic correctness or bootstrap replacement.
