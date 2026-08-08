# Bootstrap Expression Validity v1

`bootstrap-expression-validity-v1` defines the source-validity boundary immediately above the existing `bootstrap-expression-v1` flat expression stream.

The expression parser remains responsible for deterministic record construction. This contract answers a separate question: did those records represent one complete valid expression covering exactly the requested source span?

## API

`validate_expression_parse(expressions, start, length)` validates an already-parsed expression stream against its authoritative source span.

`validate_expression_span_parse(source, tokens, start, length, allocator)` composes the merged expression-span integration with the same validity contract.

## Stable result codes

| Code | Meaning |
| ---: | --- |
| 0 | Complete valid expression |
| 1 | Malformed expression-record structure |
| 2 | Parser emitted an explicit invalid node (`kind 39`) |
| 3 | Root expression does not consume exactly the requested source span |
| 4 | Requested source span is invalid |

The distinction between codes 2 and 3 is intentional. For example, `1+` requires a missing right-hand operand and therefore creates an explicit invalid node. `1 2` parses a valid leading expression but leaves a trailing token outside the root, so it fails complete-span consumption instead.

## Contract invariants

A result of zero requires all of the following:

1. `bootstrap-ast-v1` structural validation succeeds for the flat expression records.
2. No expression record has kind `39` (`invalid`).
3. The final postorder record is the root.
4. The root starts at the requested span start.
5. The root length equals the requested span length.

The contract does not diagnose semantic errors, resolve names or types, or recover by inventing missing syntax. It is a deterministic syntactic completeness gate suitable for the future bootstrap parser/AST pipeline.

## Verification

The differential test matrix executes the same validity cases through both the Merit interpreter and generated native code. It covers valid precedence, grouping, calls and constructors plus empty input, missing operands, unexpected punctuation, malformed arguments, trailing tokens, and missing group/call/constructor delimiters.
