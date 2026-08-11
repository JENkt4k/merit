# Merit Bootstrap Compiler Status

Checkpoint date: 2026-08-11

Scope: replacement-compiler development after the stable alpha reference compiler. Python remains the independent oracle; the Merit-native compiler is not yet trusted or self-hosted.

## Verified baseline entering this branch

| Metric | Result |
|---|---|
| Total tests passing | 758 passed, 1 skipped on the latest fully green hosted baseline |
| Hosted pytest | 758 passed, 1 skipped on Ubuntu / Python 3.11 / system C compiler |
| Windows native smoke | Passing on Python 3.11 / MSYS2 UCRT64 GCC |
| Compile-pass tests | Covered throughout positive semantic/project tests; whole-suite count is not yet separately instrumented |
| Compile-fail tests | Explicit negative semantic, ownership, capability, visibility, and malformed-contract cases exist; whole-suite count is not yet separately instrumented |
| Acceptance projects | 9 / 9 |
| Lexer differential cases | Complete for the versioned bootstrap token/span corpus |
| Parser differential cases | Complete for the current syntax/diagnostic corpus and all 12 expression cases |
| AST differential cases | 12 / 12 expression cases with malformed-record validation |
| HIR differential cases | 12 / 12 expression cases |
| Expression parser differential corpus | 12 / 12 |
| Canonical expression AST parity | 12 / 12 |
| Canonical expression HIR parity | 12 / 12 |
| Canonical expression MIR parity | 6 / 12 verified before this branch; 11 / 12 target on this branch |
| Interpreter/native parity | Exact for every measured replacement record stream plus 9 / 9 acceptance projects |
| Bootstrap/reference parity | 100% for explicitly covered replacement stages/cases; not a whole-language replacement percentage |
| Reference compiler source | Python alpha compiler remains the independent semantic oracle; source size is not remeasured in this checkpoint |
| Merit-native compiler source | Replacement lexer/parser/AST/HIR expression boundary is complete; MIR replacement is expanding; source size is not remeasured in this checkpoint |
| Generated C size | Not remeasured in this checkpoint; generated size remains evidence rather than an optimization target |
| Known semantic blockers | Generic specialization identity is not yet represented in bootstrap MIR; whole-function/control-flow/ownership/capability replacement and MIR-only C emission remain open |
| Reference compiler | Feature-rich alpha implementation; remains the independent semantic oracle |
| Replacement compiler | Lexer/parser/AST/HIR expression boundary complete; MIR replacement expanding |
| Self-hosted/trusted replacement | Not yet |

The old August 8 checkpoint that reported HIR as unimplemented is superseded by this document.

## Current branch objective

`bootstrap/mir-composite-expressions-v1` expands measured expression MIR from 6/12 to a target of 11/12 by adding an explicit composite-expression replacement boundary for:

- empty calls
- ordered multi-argument calls
- nested calls
- field loads
- aggregate construction
- constructor/call/field composition

The branch also adds the missing canonical HIR `field -> load_field` lowering rule. The native composite stream owns resolved symbol spans, ordered operand locals, receiver locals, deterministic root-first temporary allocation, postorder instruction emission, result types, source spans, and canonical HIR provenance.

The only expression case intentionally left outside MIR parity is `identity<i64>(1)`. HIR preserves the explicit generic argument, while the current MIR call contract does not. That information must become first-class MIR metadata before the case can be promoted honestly.

## Replacement roadmap

| Phase | Objective | Status |
|---|---|---|
| A | Lexing, syntax discovery, statement/clause operand boundaries | Proven for versioned bootstrap corpus |
| B | Expression parser and canonical AST | 12 / 12 measured corpus cases |
| C | Typed expression HIR | 12 / 12 measured corpus cases |
| D1 | Primitive expression MIR | 6 / 12 verified baseline |
| D2 | Composite expression MIR | 11 / 12 target on this branch; hosted verification required before merge |
| D3 | Generic specialization identity in MIR | Next expression milestone |
| E | Statement/function/control-flow HIR -> MIR replacement | Not yet replacement-complete |
| F | Ownership, contracts, capabilities, resources through replacement MIR | Existing reference semantics proven; native replacement still to be expanded |
| G | Deterministic C backend consumes replacement MIR only | Not yet |
| H | All nine acceptance applications through replacement compiler | Not yet |
| I | Remove Python compiler from trusted production path / self-host bootstrap | Final replacement frontier |

## Proven reference-language foundation

The existing alpha compiler already has strong verified semantics that the bootstrap compiler is replacing rather than inventing:

- exact primitive, bounded, and decimal numerics
- ownership, moves, borrows, deterministic destruction, and explicit allocation
- capabilities and contracts
- generic structs/enums/functions, traits, coherence, and generic collections within documented limits
- immutable string views and owned buffers
- filesystem capability gating
- structured diagnostics and source provenance
- C interoperability and stable-layout checks
- CFG-shaped MIR and deterministic C11 native execution
- interpreter/native differential verification
- nine acceptance applications, including the ledger application

These features define the semantic oracle for replacement work. Covered bootstrap-corpus parity must not be described as whole-language replacement until those semantic surfaces also flow through the Merit-native compiler.

## Strategy after expression MIR closes

After the expression corpus reaches 12/12 MIR parity, development should move vertically rather than accumulating isolated parser fixtures:

1. feed typed statement operands through canonical AST/HIR/MIR;
2. feed function clauses and contracts through the same path;
3. expand control flow (`if`, `while`, `match`) with exact block/terminator parity;
4. expand ownership/resource operations (`move`, `borrow`, `drop`, allocation/destruction);
5. expand capabilities and contracts;
6. expand generic and aggregate semantics across whole functions/modules;
7. make deterministic C emission consume replacement MIR;
8. move each acceptance application to the replacement pipeline until all 9/9 pass without Python semantic lowering.

This ordering maximizes vertical replacement evidence: each milestone should remove a real dependency on the Python compiler instead of merely increasing syntax coverage.

## Deliberate non-blocking future work

The following remain useful post-replacement engineering goals but do not need to block self-hosting of the documented alpha language:

- stored references and explicit lifetime parameters
- subobject-disjoint borrowing
- ownership/capability-changing destructor bodies
- per-module C objects and dependency-granular cache invalidation
- broader trait features such as associated types and specialization
- typed generic IR replacing source-rewrite monomorphization
- optimizer expansion and LLVM lowering
- package registry, formatter, language server, concurrency, and production tooling

Generated C size and replacement-source line counts remain evidence rather than optimization targets. Trust is based on deterministic contracts, differential parity, compile-pass/fail coverage, and acceptance behavior.
