# Bootstrap function clause operand contract

Contract identifier: `bootstrap-clause-v1`

## Purpose

`bootstrap-syntax-v1` indexes function-clause introducers. `bootstrap-clause-v1` adds deterministic clause envelopes and typed operand spans for the accepted alpha function clauses without performing semantic checking.

The representation is flat and source-oriented. Each `ClauseRecord` points into one shared `ClauseOperand` stream through `(first_operand, operand_count)`, matching the stage-0 storage discipline used by statement operands.

## Clause record

```text
ClauseRecord {
    kind: i32,
    start: i64,
    length: i64,
    first_operand: i64,
    operand_count: i64,
}
```

Clause kinds reuse the existing bootstrap syntax identifiers:

- `11` `effects`
- `12` `requires_caps`
- `13` `requires`
- `14` `ensures`

For list clauses, the source envelope begins at the introducer and includes the closing `]`. For contract clauses, the envelope begins at the introducer and includes the terminating `;`. If the expected terminator is absent, the deterministic recovery envelope extends to the available end of source.

## Operand record

```text
ClauseOperand {
    kind: i32,
    start: i64,
    length: i64,
}
```

Operand kinds are:

- `1` effect name
- `2` required capability name
- `3` contract expression source

Spans are byte offsets over the immutable source buffer and contain no leading or trailing whitespace because boundaries are derived from `bootstrap-lex-v1` tokens.

## Operand order

Operand order is contractual and preserves source order:

- `effects [a, b]` emits effect-name operands `a`, then `b`
- `requires_caps [a, b]` emits capability-name operands `a`, then `b`
- `requires expression;` emits one expression operand
- `ensures expression;` emits one expression operand

Empty effect/capability lists have zero operands and point at the next position in the shared operand stream. Operand ranges are contiguous and monotonic across clause records.

## Nesting and scope

Clause discovery follows the existing syntax-index boundary and records only introducers at brace depth zero. Tokens inside function, trait, impl, constructor, or other brace-delimited bodies are not emitted as function clauses by this contract.

Contract-expression termination is nesting-aware for parentheses, brackets, and braces. A semicolon terminates the contract expression only when all three nesting depths are zero. This prevents delimiters inside grouped calls, indexed forms, or direct constructors from truncating the expression operand.

## Relationship to expression AST

Expression operands remain source-oriented boundaries in this checkpoint. A subsequent integration gate may parse each kind-3 operand through `bootstrap-expression-v1` and lower it through `bootstrap-ast-v1`.

Keeping clause discovery independent from expression parsing makes failures attributable: clause tests verify role and source boundaries, while expression/AST tests verify precedence and tree meaning.

## Semantic non-goals

This contract does not determine whether:

- an effect name is declared or valid
- a required capability exists
- a required capability is sufficient for the function body
- a `requires` or `ensures` expression has boolean type
- `old()` is legal in a particular contract
- preconditions or postconditions hold

Those belong to later HIR and semantic-checking gates. The Python reference compiler remains authoritative for those accepted-alpha semantics during bootstrap.

## Recovery boundary

Malformed list contents and missing delimiters are retained as deterministic source structure rather than repaired semantically. Rich clause-specific diagnostics and multi-error recovery remain part of the later deterministic parser-recovery gate.
