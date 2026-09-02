# Merit Bootstrap Compiler Status

Checkpoint date: 2026-09-02

Scope: `v0.1.0-alpha.2` replacement-compiler development after the stable alpha reference compiler. Python remains the independent oracle; the Merit-native replacement compiler is not yet trusted or self-hosted.

## Current verified architecture

The replacement compiler is no longer accurately described as an expression-MIR experiment. The measured lexer/parser/AST/HIR/MIR fixtures remain useful differential evidence, but the active work has moved to complete source-backed function slices.

The native replacement path now represents resolved functions with versioned records for function body instructions, contracts and contract locals, instruction source/provenance, ownership bindings/effects, CFG and placement, and capability identities/effects. A source unit can publish multiple such functions in one versioned `resolved-source-function-bundle-v1` bundle.

Prepared replacement projects consume those native-resolved snapshots, validate them against the current source digest, reconstruct canonical replacement MIR, emit deterministic C, and compile native executables. Replacement project mode fails closed instead of falling back to Python semantics.

The concrete `NativeReplacementDriver` and multi-function bundle boundary are established. M1-M4 are closed and PR #109 is merged; detailed evidence remains centralized in `ALPHA2_CLOSURE.md`. Python remains responsible for orchestration at current seams and remains the independent oracle.

## Required quality dimensions

| Metric | Current status |
|---|---|
| Total tests passing | Exact counts are gate-run evidence and intentionally not frozen in this status document |
| Compile-pass tests | Positive semantic/project/native coverage remains part of the full suite; whole-suite count is not separately instrumented |
| Compile-fail tests | Negative semantic, ownership, capability, visibility, malformed-input, stale-artifact, and replacement-boundary cases remain covered; whole-suite count is not separately instrumented |
| Acceptance projects | Stable alpha acceptance projects remain part of `scripts/test.sh`; replacement migration is still incremental |
| Lexer differential cases | Proven for the versioned measured bootstrap corpus |
| Parser differential cases | Proven for the measured versioned bootstrap corpus |
| AST differential cases | Proven for measured expression/bootstrap boundaries; not a whole-language percentage |
| HIR differential cases | Proven for measured expression/bootstrap boundaries; not a whole-language percentage |
| Bootstrap/reference parity | Exact for explicitly covered replacement boundaries; not yet whole-language replacement parity |
| Reference compiler source | Python alpha compiler remains the independent semantic/diagnostic oracle |
| Merit-native compiler source | Concrete native driver carries the closed M1-M4 surfaces through replacement compilation |
| Generated C size | Evidence only; not remeasured for this checkpoint and not an optimization target |
| Known semantic blockers | M5-M10 remain open: project closure, corpus convergence, acceptance migration, production cutover, reproducibility/trust, and release audit |

## Replacement architecture evidence

| Area | Current status |
|---|---|
| Stable alpha reference compiler | Complete for documented `v0.1.0-alpha.1` subset |
| Merit-native lexer/parser bootstrap corpus | Proven for measured versioned corpora |
| Expression AST/HIR/MIR bootstrap contracts | Proven for measured differential cases; not a whole-language percentage |
| Source-backed function semantics | Native records exist for supported body/contract/ownership/CFG/capability surfaces |
| Multi-function source units | Versioned native bundle boundary complete |
| Replacement canonical MIR | Consumes native-resolved snapshots for supported functions |
| Deterministic replacement C/native build | Proven for supported replacement inputs |
| Project replacement mode | Exists and refuses reference-compiler fallback |
| Prepared-artifact freshness | Source SHA-256 checked; stale artifacts rejected |
| Production frontend interface | `NativeReplacementDriver` executable boundary complete |
| Concrete Merit-native driver attached | Complete |
| Complete accepted-alpha replacement corpus | Not yet |
| Normal Python-free production compilation | Not yet |
| Trusted/self-hosted replacement | Not yet |

The canonical GitHub gates run the full clean suite on Ubuntu and native Windows.

## Current milestone

M5 project/module/import/export/visibility closure is active. M6 corpus convergence, M7 acceptance migration, M8 production cutover, M9 reproducibility/trust, and M10 release audit follow in that order. Unsupported source must continue to fail deterministically rather than silently falling back to the reference compiler.

## Deliberate non-blocking future work

Stored references/lifetime parameters, subobject-disjoint borrowing, richer trait features, typed generic IR, LLVM, package infrastructure, formatter/LSP, concurrency, networking, and scientific array/tensor work remain outside the bootstrap critical path.

Generated C size and replacement-source line counts are evidence rather than optimization targets. Trust is based on semantic contracts, differential parity, compile-pass/fail coverage, deterministic artifacts, and acceptance behavior.
