# Merit Bootstrap Compiler Status

Checkpoint date: 2026-08-18

Scope: `v0.1.0-alpha.2` replacement-compiler development after the stable alpha reference compiler. Python remains the independent oracle; the Merit-native replacement compiler is not yet trusted or self-hosted.

## Current verified architecture

The replacement compiler is no longer accurately described as an expression-MIR experiment. The measured lexer/parser/AST/HIR/MIR fixtures remain useful differential evidence, but the active work has moved to complete source-backed function slices.

The native replacement path now represents resolved functions with versioned records for function body instructions, contracts and contract locals, instruction source/provenance, ownership bindings/effects, CFG and placement, and capability identities/effects. A source unit can publish multiple such functions in one versioned `resolved-source-function-bundle-v1` bundle.

Prepared replacement projects consume those native-resolved snapshots, validate them against the current source digest, reconstruct canonical replacement MIR, emit deterministic C, and compile native executables. Replacement project mode fails closed instead of falling back to Python semantics.

PR #75 completed multi-function bundle framing. PR #76 established a first-class `NativeReplacementDriver` executable boundary for `prepare-replacement`, replacing the former arbitrary command-vector producer interface. Python remains responsible only for process orchestration, bundle validation, source identity, and atomic artifact publication at this seam.

## Evidence and gates

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
| Concrete Merit-native driver attached | Next milestone |
| Complete accepted-alpha replacement corpus | Not yet |
| Normal Python-free production compilation | Not yet |
| Trusted/self-hosted replacement | Not yet |

The authoritative GitHub Local Gate runs the full clean Ubuntu/Python 3.11/system-C gate plus a focused Windows/MSYS2 UCRT64 GCC native smoke. PR #76 passed Local Gate run 177 before merge.

## Immediate milestone

Build or attach the concrete Merit-native source-unit frontend executable behind `NativeReplacementDriver` and prove this complete path without Python semantic lowering:

```text
source unit
 -> native frontend driver
 -> resolved multi-function bundle
 -> prepared project artifacts
 -> canonical replacement MIR
 -> deterministic C
 -> native executable
```

The driver must be a real compiler boundary, not a fixture protocol adapter. Unsupported source must fail deterministically rather than silently falling back to the reference compiler.

## Strategy after the driver is attached

Expand vertically through the documented alpha language: statements and control flow, ownership/resource operations, contracts and capabilities, exact numerics, aggregates and payload enums, generics/traits, and module/project interactions. For each promoted surface, keep positive and negative/fail-closed tests plus reference/interpreter/native differential evidence as applicable.

Move acceptance applications onto the replacement path incrementally. Only after the accepted/rejected alpha corpus and acceptance behavior agree should normal production compilation default to the replacement compiler. Stage equivalence and self-hosting follow trust; they do not substitute for it.

## Deliberate non-blocking future work

Stored references/lifetime parameters, subobject-disjoint borrowing, richer trait features, typed generic IR, LLVM, package infrastructure, formatter/LSP, concurrency, networking, and scientific array/tensor work remain outside the bootstrap critical path.

Generated C size and replacement-source line counts are evidence rather than optimization targets. Trust is based on semantic contracts, differential parity, compile-pass/fail coverage, deterministic artifacts, and acceptance behavior.
