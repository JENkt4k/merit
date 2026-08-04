# Replacement compiler bootstrap

## Objective

Normal production compilation will eventually use a compiler written in Merit rather than the Python-hosted reference implementation. Bootstrap work must preserve the accepted alpha semantics and prove each replacement stage differentially before it displaces its Python counterpart.

## Versioned source contract: bootstrap-lex-v1

The first replacement slice consumes an owned UTF-8 `Buffer` and produces typed `Token` records. Source locations are zero-based byte offsets so diagnostics remain deterministic for ASCII and multibyte UTF-8 input without depending on host character indexing.

```text
Token { kind: i32, start: i64, length: i64 }
```

Kinds are identifier/keyword (`1`), exact numeric literal (`2`), quoted string (`3`), punctuation (`4`), and invalid unterminated string (`5`). Numeric spans accept decimal fractions and signed decimal exponents after an initial digit sequence; a leading sign remains punctuation for the parser to interpret contextually. ASCII whitespace and `//` line comments are discarded. Strings include their quotes in the byte span and skip the byte following a backslash while scanning. The sequences `->`, `=>`, `==`, `!=`, `>=`, `<=`, and `::` are maximal two-byte punctuation spans; other punctuation is one byte. Every emitted span is non-empty and contained within the input buffer.

`examples/projects/bootstrap_lexer` is the executable contract fixture. Its interpreter and native output must match, allocation must remain capability-gated, owned token storage must be destroyed exactly once, and generated C must retain ordered source reads before token insertion.

## Versioned syntax contract: bootstrap-syntax-v1

The initial parser boundary recognizes top-level declaration introducers while tracking brace depth, so trait/impl/function bodies cannot leak nested declarations into the module surface.

```text
SyntaxNode { kind: i32, start: i64, length: i64 }
```

Kinds are module (`1`), function (`2`), struct (`3`), enum (`4`), capability (`5`), decimal (`6`), bounded (`7`), trait (`8`), impl (`9`), destructor (`10`), effects clause (`11`), required-capabilities clause (`12`), precondition (`13`), postcondition (`14`), let (`20`), var (`21`), return (`22`), print (`23`), drop (`24`), if (`25`), while (`26`), match (`27`), with-capability (`28`), and replace (`29`). A declaration node begins at its keyword and extends through the following identifier when present; clause and initial statement nodes span their keyword. This syntax contract remains an index, not yet a complete grammar tree; parameters, fields, clause operands, statement operands, and expressions remain the next parser slices.

The differential corpus compares every syntax kind and byte span with an independent reference, including a fixture containing all declaration kinds and a nested impl method that must not appear as a top-level function.

`ParseDiagnostic { code, start, length }` is the initial deterministic diagnostic boundary. Codes are missing declaration name (`1`), unexpected closing brace (`2`), unclosed brace at end of input (`3`), and invalid unterminated string (`4`). Diagnostics use source byte spans; the end-of-input unclosed-brace diagnostic has a zero-length span at `buffer_len(source)`. Interpreter and native diagnostic records must exactly match the independent corpus oracle.

## Staged replacement gates

1. Extend `bootstrap-lex-v1` to the complete accepted token vocabulary and differential fixtures.
2. Expand `bootstrap-syntax-v1` from its top-level declaration index into typed declaration, clause, statement, and expression records with deterministic diagnostics.
3. Construct versioned typed HIR and MIR that can be compared with the Python reference output.
4. Emit deterministic C and prove stage-0/stage-1 equivalence.
5. Expand the subset until the replacement compiler builds the accepted alpha corpus without Python in the normal compilation path.

Hosted CI, LLVM, and unrelated language expansion remain deferred while these gates are active.
