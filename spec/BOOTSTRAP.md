# Replacement compiler bootstrap

## Objective

Normal production compilation will eventually use a compiler written in Merit rather than the Python-hosted reference implementation. Bootstrap work must preserve the accepted alpha semantics and prove each replacement stage differentially before it displaces its Python counterpart.

## Versioned source contract: bootstrap-lex-v1

The first replacement slice consumes an owned UTF-8 `Buffer` and produces typed `Token` records. Source locations are zero-based byte offsets so diagnostics remain deterministic for ASCII and multibyte UTF-8 input without depending on host character indexing.

```text
Token { kind: i32, start: i64, length: i64 }
```

Kinds are identifier (`1`), decimal integer (`2`), quoted string (`3`), punctuation (`4`), and invalid unterminated string (`5`). ASCII whitespace and `//` line comments are discarded. Strings include their quotes in the byte span and skip the byte following a backslash while scanning. Every emitted span is non-empty and contained within the input buffer.

`examples/projects/bootstrap_lexer` is the executable contract fixture. Its interpreter and native output must match, allocation must remain capability-gated, owned token storage must be destroyed exactly once, and generated C must retain ordered source reads before token insertion.

## Staged replacement gates

1. Extend `bootstrap-lex-v1` to the complete accepted token vocabulary and differential fixtures.
2. Parse the bootstrap language subset into typed syntax records with deterministic diagnostics.
3. Construct versioned typed HIR and MIR that can be compared with the Python reference output.
4. Emit deterministic C and prove stage-0/stage-1 equivalence.
5. Expand the subset until the replacement compiler builds the accepted alpha corpus without Python in the normal compilation path.

Hosted CI, LLVM, and unrelated language expansion remain deferred while these gates are active.
