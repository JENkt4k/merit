# Merit Roadmap

## `v0.1.0-alpha.1` release gate

The first alpha closed a deterministic, resource-safe component-language subset. Its ordered gates are complete: portable left-to-right expression lowering, unique semantic binding IDs, the ephemeral returned-borrow boundary, release-document consolidation, the multi-module exact-decimal ledger acceptance application, arbitrary-precision numeric reference coverage, and the final local/specification audit.

The alpha does not require stored references, lifetime parameters, async, concurrency, networking, LLVM, trait objects, specialization, tensors, or package-registry work.

## Proven foundation

- Epoch I established exact numerics, bounded values, contracts, capabilities, stable layouts, interpretation, native C generation, and differential testing.
- Epoch II established projects/modules, visibility, enums, typed propagation, strings, owned buffers, explicit allocation, filesystem reads, and CFG-shaped MIR.
- Epoch III established explicit generics and coherent traits, generic collections, typed filesystem errors, allocator identity, destructors, stable shared libraries, structured diagnostics, qualified imports, object caching, ordered expression lowering, binding IDs, and validated ephemeral borrowed returns.

## After the first alpha

### Active `v0.1.0-alpha.2` replacement compiler

The objective is unchanged: eliminate Python semantic authority from normal production compilation while retaining the Python compiler as an independent oracle until the replacement qualifies as trusted. Do not broaden the language to achieve bootstrap.

Early bootstrap work established deterministic native lexer/parser records and canonical expression AST/HIR/MIR contracts. Development has since moved vertically through real source-backed functions and projects rather than waiting for every isolated stage fixture to reach whole-language coverage first.

### Completed replacement boundaries

1. Merit-native lexer and source-oriented statement/clause/expression discovery for the measured bootstrap corpus.
2. Canonical expression AST/HIR/MIR contracts with differential Python-oracle and interpreter/native evidence for their measured cases.
3. Source-backed function records carrying body instructions and source provenance.
4. Function contracts and contract-local metadata in the native path.
5. Whole-function assembly records and deterministic instruction-source identity.
6. Ownership bindings/effects and path-sensitive control-flow integration.
7. CFG records and deterministic placement integrated with resolved source functions.
8. Capability identities/effects carried through the resolved source-function boundary.
9. Versioned resolved-source-function snapshots and multi-function bundle framing.
10. Canonical replacement MIR reconstruction and deterministic C/native execution from native-resolved artifacts.
11. Production project replacement mode that consumes prepared native artifacts and refuses Python fallback.
12. Source-digest validation and atomic preparation/publication of replacement artifacts.
13. A first-class `NativeReplacementDriver` executable boundary with a concrete Merit-native replacement driver.
14. Complete documented Alpha.1 statement/control-flow, resource/lifecycle, exact-numeric/aggregate, generic/trait, and module/project/export surfaces through replacement compilation (M1-M5).
15. Canonical accepted/rejected Alpha.1 same-source corpus convergence between the independent reference compiler and production replacement compiler, including deterministic replacement-artifact evidence (M6).

### Immediate critical path

`ALPHA2_CLOSURE.md` is the authoritative detailed work queue. **M1-M6 are closed.**

The current frontier is **M7 acceptance-project migration**: all 10 canonical acceptance applications must compile and run through replacement mode with no Python semantic lowering or silent fallback. The exact-decimal `ledger_app` is mandatory evidence. `docs/M7_ACCEPTANCE_MIGRATION.md` defines the implementation and closure contract.

M7 is followed by M8 normal production-path cutover, M9 stage reproducibility/trust, and M10 the Alpha.2 release audit. Alpha.2 is not complete or trusted, and self-hosting begins only after the trust gate.

### Documentation path

The user-facing programming manual lives under `docs/manual/` and should advance one stable semantic checkpoint behind implementation. Manual examples should be executable repository examples or otherwise gated so documentation drift becomes a test failure rather than silent prose decay.

### Trust criteria

Trust is based on deterministic typed contracts, accepted/rejected corpus parity, interpreter/native agreement, stable artifact framing, compile-pass/fail coverage, real acceptance behavior, and reproducible stages. M6 satisfies the corpus-convergence component; M7-M10 close the remaining application, production, reproducibility, and release boundaries.

Persistent hosted CI is a verification aid for the local/reproducibility gates; it does not replace bootstrap trust criteria.

Async, concurrency, networking, LLVM, richer trait machinery, scientific arrays/tensors, registry/package infrastructure, formatter/LSP work, and broad platform automation remain post-alpha roadmap topics. They must not displace semantic correctness or replacement of the normal compiler path.