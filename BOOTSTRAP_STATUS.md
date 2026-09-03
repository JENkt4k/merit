# Merit Bootstrap Compiler Status

Checkpoint date: 2026-09-03

Scope: `v0.1.0-alpha.2` replacement-compiler development after the stable alpha reference compiler. Python remains the independent oracle; the Merit-native replacement compiler is not yet trusted or self-hosted.

## Current verified architecture

The replacement compiler is no longer accurately described as an expression-MIR experiment. The measured lexer/parser/AST/HIR/MIR fixtures remain useful differential evidence, but the active work now reaches complete source-backed semantic slices, project-wide resolution, and same-source corpus convergence.

The native replacement path represents resolved functions and projects with versioned records for bodies, contracts, provenance, ownership, CFG/placement, capabilities, exact numerics, aggregates/resources, generics/traits, imports/visibility, and export/ABI identity. Prepared replacement projects validate native-resolved artifacts against current source, reconstruct canonical replacement MIR, emit deterministic C, and compile native executables. Replacement mode fails closed instead of falling back to Python semantics.

M1-M5 close the documented Alpha.1 semantic and project surfaces. M6 closes the canonical accepted/rejected same-source corpus convergence boundary: accepted programs reach reference and replacement native execution with observable parity and repeated deterministic replacement artifacts; rejected programs are rejected independently and deterministically. Detailed evidence remains centralized in `ALPHA2_CLOSURE.md` and `docs/ALPHA1_CORPUS_CONVERGENCE.md`.

## Required quality dimensions

| Metric | Current status |
|---|---|
| Total tests passing | Exact counts are gate-run evidence and intentionally not frozen here |
| Compile-pass tests | Positive semantic/project/native coverage remains part of the full suite |
| Compile-fail tests | Negative semantic, ownership, capability, visibility, malformed-input, stale-artifact, and replacement-boundary cases remain covered |
| Acceptance projects | 10 canonical projects remain in the acceptance gate; replacement migration is M7 |
| Lexer/parser differential cases | Proven for the versioned measured bootstrap corpora |
| AST/HIR differential cases | Proven for measured boundaries; not used as whole-language percentages |
| Bootstrap/reference parity | Canonical M6 same-source accepted/rejected corpus convergence is closed |
| Reference compiler source | Python Alpha.1 compiler remains the independent semantic/diagnostic oracle |
| Merit-native compiler source | Concrete native driver carries M1-M6 replacement evidence |
| Known semantic blockers | No unexplained M6 corpus discrepancy remains; M7-M10 remain open |

## Replacement architecture evidence

| Area | Current status |
|---|---|
| Stable Alpha.1 reference compiler | Complete for documented subset |
| Merit-native lexer/parser bootstrap corpus | Proven for measured versioned corpora |
| Source-backed function semantics | Closed for documented Alpha.1 replacement surface |
| Multi-function/project resolution | Closed through M5 |
| Replacement canonical MIR | Consumes native-resolved artifacts for documented Alpha.1 surface |
| Deterministic replacement C/native build | Proven for covered replacement inputs |
| Project replacement mode | Exists and refuses reference-compiler fallback |
| Prepared-artifact freshness | Source digests checked; stale artifacts rejected |
| Complete accepted/rejected Alpha.1 convergence corpus | CLOSED in M6 |
| All canonical acceptance projects through replacement | M7 OPEN |
| Normal Python-free production compilation | M8 OPEN |
| Stage reproducibility/trust | M9 OPEN |
| Trusted/self-hosted replacement | Not yet |

The canonical GitHub gates run the full clean suite on Ubuntu and native Windows.

## Current milestone

**M7 acceptance migration is active.** All 10 canonical acceptance projects must compile and run through production replacement mode without Python semantic lowering or silent fallback. The exact-decimal `ledger_app` is mandatory evidence. See `docs/M7_ACCEPTANCE_MIGRATION.md` for the implementation and closure contract.

M8 production cutover, M9 reproducibility/trust, and M10 release audit follow in that order. Unsupported source must continue to fail deterministically rather than silently falling back to the reference compiler.

## Deliberate non-blocking future work

Stored references/lifetime parameters, subobject-disjoint borrowing, richer trait features, typed generic IR, LLVM, package infrastructure, formatter/LSP, concurrency, networking, and scientific array/tensor work remain outside the bootstrap critical path.

Generated C size and replacement-source line counts are evidence rather than optimization targets. Trust is based on semantic contracts, differential parity, compile-pass/fail coverage, deterministic artifacts, real acceptance behavior, production cutover, and reproducible stages.