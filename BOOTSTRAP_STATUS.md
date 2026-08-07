# Merit Bootstrap Compiler Status

Checkpoint date: 2026-08-07

Scope: `v0.1.0-alpha.2` replacement-compiler development. Python remains the independent reference oracle; the Merit-native compiler is not yet trusted or self-hosted.

| Metric | Current result |
|---|---|
| Hosted clean-environment regression suite | 671 passed, 1 skipped on Ubuntu / Python 3.11 / system C compiler |
| Windows native smoke gate | Passing on Windows / Python 3.11 / MSYS2 UCRT64 GCC |
| Compile-pass tests | Not yet separately instrumented across the whole suite; tracked as a reporting blocker |
| Compile-fail tests | Not yet separately instrumented across the whole suite; bootstrap capability and malformed-contract cases are explicit |
| Acceptance projects | 9 / 9 |
| Lexer differential cases | Complete for the versioned bootstrap token/span corpus |
| Parser differential cases | Complete for the currently covered syntax/diagnostic corpus |
| Expression differential cases | Complete for all 12 manifest `bootstrap-corpus-v1` expression cases in the current parser subset |
| AST differential cases | 12 / 12 manifest expression cases plus nested-group provenance and malformed-record validation |
| Canonical AST parity | Merit interpreter and generated native flat AST reconstruct exactly to the Python `bootstrap-ast-v1` tree and compact JSON oracle |
| HIR differential cases | 0; bootstrap HIR not implemented |
| Interpreter/native parity | 9 / 9 acceptance projects plus the versioned bootstrap differential corpus |
| Bootstrap/reference parity | 100% for the explicitly covered token/syntax/diagnostic/expression/AST corpus; not a whole-language percentage |
| Specification implemented | `bootstrap-lex-v1`; partial `bootstrap-syntax-v1`; partial `bootstrap-expression-v1`; expression-stage `bootstrap-ast-v1` lowering |
| Known semantic blockers | typed statement/clause operands; qualified and multi-type constructors; expression recovery; trivia-preserving CST; whole-alpha AST coverage; HIR/MIR bootstrap stages; whole-suite pass/fail instrumentation |

## Native AST checkpoint

The Merit bootstrap now lowers accepted `bootstrap-expression-v1` records into deterministic flat `AstNodeRecord` storage. Parenthesized parser groups do not survive as semantic nodes; their spans are retained as ordered grouping provenance. The flat representation is intentionally stage-0-friendly and non-recursive, but its externally meaningful contract is the recursive `bootstrap-ast-v1` tree.

Differential tests prove four layers for every manifest expression case:

1. the independent Python parser produces the expected postorder expression records;
2. Merit interpreter lowering produces the expected flat AST records;
3. generated native C produces byte-for-byte equivalent flat AST records;
4. those flat records reconstruct to the same canonical tree and compact JSON as `merit.bootstrap.ast_contract`.

Malformed record streams are rejected with stable native contract codes for empty input, invalid spans, unknown kinds, malformed groups, atom-child violations, and invalid forward child references.

## Public collection visibility checkpoint

The AST API exposed an existing project-loader defect: `Vec<T>` was rejected from a public signature because the lowered monomorph name `Vec__T` was treated as an unrelated private type. Public-surface visibility now propagates recursively through the builtin vector container: `Vec<T>` is public exactly when `T` is public. Wrapping a private type in one or more vectors does not launder its visibility. Focused positive and negative project tests lock this rule down.

Generated sizes and source-line counts are evidence rather than optimization targets and are intentionally omitted from this checkpoint until the replacement compiler source is remeasured consistently. Do not use covered-corpus parity to claim bootstrap replacement, trust, or self-hosting.
