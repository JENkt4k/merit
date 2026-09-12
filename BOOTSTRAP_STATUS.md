# Merit Bootstrap Compiler Status

Checkpoint date: 2026-09-12

Scope: `v0.1.0-alpha.2` release closure after replacement-compiler trust
qualification. Python remains the independent oracle. The Merit-native
replacement compiler is trusted for the documented Alpha.1 production surface
but is not self-hosted.

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
| Acceptance projects | 10/10 canonical projects pass replacement execution; M7 is closed |
| Lexer differential cases | Proven for the versioned measured bootstrap corpora |
| Parser differential cases | Proven for the versioned measured bootstrap corpora |
| AST differential cases | Proven for measured boundaries; not used as whole-language percentages |
| HIR differential cases | Proven for measured boundaries; not used as whole-language percentages |
| Bootstrap/reference parity | Canonical M6 same-source accepted/rejected corpus convergence is closed |
| Reference compiler source | Python Alpha.1 compiler remains the independent semantic/diagnostic oracle |
| Merit-native compiler source | Concrete native driver carries M1-M9 production and trust evidence |
| Generated C size | Tracked as build evidence rather than an optimization target |
| Known semantic blockers | None for the documented Alpha.1 production surface; M10 is release-process closure |

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
| All canonical acceptance projects through replacement | M7 CLOSED (PR #113) |
| Normal Python-free production compilation | M8 CLOSED (PR #114) |
| Stage reproducibility/trust | M9 CLOSED (PR #115) |
| Trusted/self-hosted replacement | Trusted for the documented Alpha.1 production surface; not self-hosted |

The canonical GitHub gates run the full clean suite on Ubuntu and native Windows.

## Current milestone

**M10 release audit is active.** Stage 0 produces stage 1, stage 1 reproduces
stage 2, and canonical compiler artifacts agree under
`docs/M9_REPRODUCIBILITY.md` on clean Ubuntu and native Windows.

The remaining Alpha.2 boundary is final release validation, manual merge, and
tagging. Unsupported source must continue to fail deterministically rather than
silently falling back to the reference compiler.

## Deliberate non-blocking future work

Stored references/lifetime parameters, subobject-disjoint borrowing, richer trait features, typed generic IR, LLVM, package infrastructure, formatter/LSP, concurrency, networking, and scientific array/tensor work remain outside the bootstrap critical path.

Generated C size and replacement-source line counts are evidence rather than optimization targets. Trust is based on semantic contracts, differential parity, compile-pass/fail coverage, deterministic artifacts, real acceptance behavior, production cutover, and reproducible stages.
