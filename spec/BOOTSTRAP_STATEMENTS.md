# Bootstrap statement operand contract

Contract identifier: `bootstrap-statement-v1`

## Purpose

`bootstrap-syntax-v1` identifies deterministic statement envelopes. `bootstrap-statement-v1` adds typed operand boundaries without yet performing name resolution, type checking, ownership analysis, capability checking, or HIR lowering.

The contract is intentionally flat and source-oriented. A statement record points into one shared operand stream by `(first_operand, operand_count)`. This keeps stage-0 ownership non-recursive and makes interpreter/native differential comparison straightforward.

## Statement record

```text
StatementRecord {
    kind: i32,
    start: i64,
    length: i64,
    first_operand: i64,
    operand_count: i64,
}
```

The statement kinds reuse the existing bootstrap syntax identifiers:

- `20` `let`
- `21` `var`
- `22` `return`
- `23` `print`
- `24` `drop`
- `25` `if`
- `26` `while`
- `27` `match`
- `28` `with capability`
- `29` `replace`

The statement source span is the same deterministic envelope used by `bootstrap-syntax-v1`: simple statements include their terminating semicolon, while control statements include the opening body brace.

## Operand record

```text
StatementOperand {
    kind: i32,
    start: i64,
    length: i64,
}
```

Operand kinds are:

- `1` binding name
- `2` declared type
- `3` expression source
- `4` capability name

Operand spans contain no leading or trailing whitespace because they are derived from token boundaries. Expression operands preserve grouping punctuation when it is part of the operand source.

## Operand order

Operand order is contractual:

- `let` / `var`: binding name, declared type when present, initializer expression when present
- `return`: returned expression
- `print`: printed expression
- `drop`: dropped expression
- `if`: condition expression
- `while`: condition expression
- `match`: subject expression
- `with capability`: capability name
- `replace`: target expression, replacement expression

A record with zero operands points at the next operand-stream position and has `operand_count == 0`. Record operand ranges are contiguous and monotonic across the stream.

## Delimiter rules

Statement operand discovery is nesting-aware for parentheses, brackets, and braces. Delimiters inside nested calls, indexing forms, constructor bodies, or grouped expressions do not terminate an outer operand.

This matters especially for `replace(target, replacement)`: only the top-level comma separates its two expression operands. Commas inside calls or nested bracketed forms remain part of the corresponding operand.

## Relationship to expression AST

`bootstrap-statement-v1` records **where** expression operands occur and what role they play. It does not duplicate the expression parser or embed recursive expression trees in statement storage.

The next integration gate may lower each kind-3 operand through the versioned `bootstrap-expression-v1` / `bootstrap-ast-v1` path. Keeping the statement and expression contracts separate lets differential tests detect whether a defect belongs to statement boundary discovery or expression parsing.

## Recovery and malformed input

This checkpoint preserves the existing deterministic envelope behavior. Missing delimiters use the available source extent rather than inventing semantic nodes. Rich statement-specific recovery diagnostics remain a later parser gate.

## Non-goals

This contract does not define:

- symbol resolution
- semantic types
- ownership or move state
- capability authorization
- contract evaluation
- HIR or MIR
- statement-specific recovery diagnostics
- recursive statement-owned expression storage

Those remain later versioned gates.
