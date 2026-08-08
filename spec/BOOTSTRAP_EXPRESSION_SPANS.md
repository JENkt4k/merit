# Bootstrap expression-span integration contract

## Version

`bootstrap-expression-span-v1`

## Purpose

Statement and function-clause discovery intentionally stores expression operands as byte spans rather than embedding expression trees. This contract connects those source-oriented boundaries to the existing `bootstrap-expression-v1` parser and `bootstrap-ast-v1` lowering without duplicating expression grammar or making statement/clause discovery responsible for recursive expression storage.

The boundary applies to kind-3 `StatementOperand` and `ClauseOperand` records.

## Inputs

The adapter consumes:

- the immutable source `Buffer` used to discover the operand;
- the complete `bootstrap-lex-v1` token stream for that source;
- a zero-based byte `start`;
- a byte `length`;
- an allocator under the `allocate` capability.

The source span is authoritative. The adapter selects only tokens whose complete byte span is contained within `[start, start + length)`. Token locations are not rebased: parser and AST records retain their original absolute source offsets.

## Parser integration

`expression_span_tokens` produces a temporary filtered token vector. `parse_expression_span` delegates that vector to the existing `parse_expression_tokens` precedence parser. The adapter does not contain a second expression grammar.

Span filtering is semantically important. A statement condition such as:

```text
if value != limit { ... }
```

has an operand span ending after `limit`. The following `{` therefore cannot be consumed as the direct-constructor postfix `limit { ... }`. The same rule isolates contract expressions from their terminating semicolon and neighboring clauses.

## AST integration

`validate_expression_span_ast` parses the bounded operand and delegates validation to `validate_expression_ast_records`.

`lower_expression_span_ast` parses the bounded operand and delegates lowering to `lower_expression_ast_records`. Therefore grouping removal, grouping provenance, child indices, and expression kind semantics remain exactly those of `bootstrap-ast-v1`.

The adapter owns and destroys its temporary filtered token and expression vectors. Returned expression or AST vectors are owned by the caller under the existing collection rules.

## Differential gate

The integration gate obtains statement and clause expression spans from independent Python token-level oracles. For every kind-3 operand it:

1. slices the oracle source bytes at the recorded span;
2. parses that isolated expression with the independent Python expression oracle;
3. translates relative oracle byte offsets back to absolute source offsets;
4. independently constructs the expected flat AST records;
5. compares the complete Merit expression record stream and AST record stream through the interpreter;
6. repeats the comparison against the generated native executable.

The corpus includes arithmetic precedence, calls, field access, direct constructors, grouped expressions, comparisons, replacement operands, preconditions, postconditions, and conditions immediately followed by a block brace.

## Non-goals

This checkpoint does not add expression syntax, semantic typing, name resolution, capability authorization, contract evaluation, deterministic malformed-expression recovery, or HIR lowering. Qualified/multi-type constructors and the remaining expression-recovery work stay in `bootstrap-expression-v1`.

This contract proves composition of already-versioned parser layers. It does not make the current syntax index a trivia-preserving CST or complete the whole accepted-alpha AST.
