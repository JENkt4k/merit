# Replacement compiler bootstrap

## Objective

Normal production compilation will eventually use a compiler written in Merit rather than the Python-hosted reference implementation. Bootstrap work must preserve the accepted alpha semantics and prove each replacement stage differentially before it displaces its Python counterpart.

## Compiler authority

- The Python implementation is the executable reference and semantic/diagnostic oracle during bootstrap.
- The Merit-native implementation is the bootstrap compiler. Compiling programs does not make it authoritative.
- A trusted compiler must pass the complete accepted and rejected corpora, defined diagnostic contracts, runtime equivalence, deterministic output, and stage-0/stage-1 gates with no unexplained differences.
- A self-hosted compiler is a later trusted compiler that reproducibly compiles its own source. Self-hosting alone is not correctness evidence.

When implementations disagree, the specification is authoritative. Add a minimal regression, determine which implementation or rule is wrong, and document intentional changes; never automatically modify the reference to match bootstrap convenience.

## Required pipeline

```text
Source
-> Lexer
-> Tokens
-> Concrete Syntax Tree
-> AST
-> HIR
-> Semantic analysis
-> Ownership / contracts / capabilities
-> MIR
-> Deterministic C lowering
-> Native compilation
```

The CST preserves delimiters, trivia, exact spans, recovery structure, and diagnostic provenance without semantic decisions. AST removes irrelevant concrete distinctions while remaining source-oriented. HIR carries resolved symbols, binding IDs, types, normalized calls/constructors, contracts, capabilities, ownership modes, numeric policies, and provenance. MIR alone carries backend-neutral ordered operations, temporaries, transfers, drops, checks, hazards, and deterministic terminators. C lowering consumes MIR and does not reconstruct language meaning.

## Versioned source contract: bootstrap-lex-v1

The first replacement slice consumes an owned UTF-8 `Buffer` and produces typed `Token` records. Source locations are zero-based byte offsets so diagnostics remain deterministic for ASCII and multibyte UTF-8 input without depending on host character indexing.

```text
Token { kind: i32, start: i64, length: i64 }
```

Kinds are identifier/keyword (`1`), exact numeric literal (`2`), quoted string (`3`), punctuation (`4`), and invalid unterminated string (`5`). Numeric spans accept decimal fractions and signed decimal exponents after an initial digit sequence; a leading sign remains punctuation for the parser to interpret contextually. ASCII whitespace and `//` line comments are discarded. Strings include their quotes in the byte span and skip the byte following a backslash while scanning. The sequences `->`, `=>`, `==`, `!=`, `>=`, `<=`, and `::` are maximal two-byte punctuation spans; other punctuation is one byte. Every emitted span is non-empty and contained within the input buffer.

`examples/projects/bootstrap_lexer` is the executable contract fixture. Its interpreter and native output must match, allocation must remain capability-gated, owned token storage must be destroyed exactly once, and generated C must retain ordered source reads before token insertion.

## Versioned syntax contract: bootstrap-syntax-v1

The initial parser boundary recognizes top-level declaration introducers while tracking brace depth, so trait/impl/function bodies cannot leak nested declarations into the module surface.

This stream is a parser index prototype, not the CST: `bootstrap-lex-v1` currently discards whitespace and comments. The explicit CST gate must retain or reconstruct trivia from the immutable source buffer and token gaps before AST work begins. `SyntaxNode` kinds must not accumulate semantic resolution, ownership, or backend meaning.

```text
SyntaxNode { kind: i32, start: i64, length: i64 }
```

Kinds are module (`1`), function (`2`), struct (`3`), enum (`4`), capability (`5`), decimal (`6`), bounded (`7`), trait (`8`), impl (`9`), destructor (`10`), effects clause (`11`), required-capabilities clause (`12`), precondition (`13`), postcondition (`14`), let (`20`), var (`21`), return (`22`), print (`23`), drop (`24`), if (`25`), while (`26`), match (`27`), with-capability (`28`), and replace (`29`). A declaration node begins at its keyword and extends through the following identifier when present. Clause nodes span their keyword. Simple statement envelopes extend through their semicolon; control envelopes extend through their opening body brace. An unterminated statement extends deterministically to end of input. Parameters, fields, typed statement operands, and precedence-aware expressions remain the next parser slices.

The differential corpus compares every syntax kind and byte span with an independent reference, including a fixture containing all declaration kinds and a nested impl method that must not appear as a top-level function.

`ParseDiagnostic { code, start, length }` is the initial deterministic diagnostic boundary. Codes are missing declaration name (`1`), unexpected closing brace (`2`), unclosed brace at end of input (`3`), and invalid unterminated string (`4`). Diagnostics use source byte spans; the end-of-input unclosed-brace diagnostic has a zero-length span at `buffer_len(source)`. Interpreter and native diagnostic records must exactly match the independent corpus oracle.

## Versioned expression contract: bootstrap-expression-v1

`ExpressionNode { kind, start, length, left, right }` is a postorder typed parser tree with child indices. Atom kinds are identifier (`30`), exact numeric (`31`), string (`32`), explicit parenthesized group (`33`), call (`34`), field access (`35`), single-type generic application (`36`), sequence/list pair (`37`), field initializer (`38`), invalid/missing primary (`39`), and direct struct constructor (`70`). Binary kinds are equality (`40`), inequality (`41`), greater-or-equal (`42`), less-or-equal (`43`), greater (`44`), less (`45`), addition (`50`), subtraction (`51`), multiplication (`60`), and division (`61`). Call nodes point to their callee and a `-1`, single argument, or postorder argument-list root. Field nodes point to their receiver and identifier node. Constructor nodes point to their type expression and field-initializer/list root.

Postfix generic application, calls, constructors, and fields bind before multiplication/division, which bind before addition/subtraction; comparisons bind last. Arithmetic operators associate left and the accepted grammar permits at most one comparison at this stage. Parentheses remain explicit because this is parser structure. The future CST-to-AST lowering will remove semantically irrelevant grouping nodes while retaining provenance. Qualified enum constructors, multi-type generic constructors, and deterministic malformed-postfix/operator recovery are not yet implemented, so the expression gate remains partial.

## Staged replacement gates

The normative implementation order is the 15-step `v0.1.0-alpha.2` list in `ROADMAP.md`. Each stage requires independent accepted/rejected corpora and canonical comparison at the token/span, syntax/diagnostic, AST, HIR, semantic, ownership, capability, contract, numeric, MIR, generated-C, and runtime layers where applicable.

Stable diagnostic codes and primary spans must match. Explanatory wording need not match unless a specification explicitly makes it contractual. Parser robustness must eventually cover arbitrary bytes, malformed UTF-8 under the source contract, truncation, deep nesting, repeated operators, malformed generics/contracts/capabilities, huge numerics, and multiple-error recovery without crashes, hangs, or unbounded resource use. Fuzzing remains local and manually invoked.

Bootstrap replacement is complete only when normal compilation no longer invokes Python and the full clean-checkout local gate passes through the Merit-native compiler. Python remains available afterward as an oracle. Trust additionally requires repeated corpus passes, stable serialized IRs, deterministic stage agreement, explicit limitations, successful acceptance projects, and a release cycle. Self-hosting additionally requires reproducible stage-1/stage-2 compiler equivalence and the complete corpus under stage 2.

Hosted CI, LLVM, and unrelated language expansion remain deferred while these gates are active.
