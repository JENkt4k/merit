# Merit Bootstrap Compiler Status

Checkpoint date: 2026-08-04

Scope: `v0.1.0-alpha.2` replacement-compiler development. Python is the reference oracle; the Merit-native compiler is not yet trusted or self-hosted.

| Metric | Current result |
|---|---|
| Total tests passing | 376 |
| Compile-pass tests | Not yet separately instrumented across the whole suite; tracked as a reporting blocker |
| Compile-fail tests | Not yet separately instrumented across the whole suite; three bootstrap capability compile-fail cases are explicit |
| Acceptance projects | 9 / 9 |
| Lexer differential cases | 12 / 12 reference/bootstrap/interpreter/native cases |
| Parser differential cases | 12 / 12 syntax/diagnostic cases |
| Expression differential cases | 13 / 13 precedence/tree cases |
| AST differential cases | 0; AST boundary not implemented |
| HIR differential cases | 0; bootstrap HIR not implemented |
| Interpreter/native parity | 9 / 9 acceptance projects; 12 / 12 bootstrap corpus cases |
| Bootstrap/reference parity | 100% for the covered 12-case token/syntax/diagnostic corpus; not a whole-language percentage |
| Reference compiler source | 3,458 Python lines across 10 files |
| Merit-native compiler source | 968 Merit lines across 3 files |
| Generated C size | bootstrap fixture: 214,448 bytes / 4,103 lines; ledger fixture: 29,937 bytes / 402 lines |
| Specification implemented | `bootstrap-lex-v1`; partial `bootstrap-syntax-v1`; partial `bootstrap-expression-v1` including direct constructors and single-type generic calls |
| Known semantic blockers | qualified/multi-type constructors; typed statement/clause operands; expression recovery; trivia-preserving CST; AST/HIR/MIR bootstrap stages; whole-suite pass/fail instrumentation |

Generated sizes are evidence, not optimization targets. Update this table after every cohesive bootstrap checkpoint. Do not use covered-corpus parity to claim bootstrap replacement, trust, or self-hosting.
