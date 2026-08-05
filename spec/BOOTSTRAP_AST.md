# Bootstrap AST contract

Contract identifier: `bootstrap-ast-v1`

## Purpose

`bootstrap-expression-v1` is a source-parser record stream. It intentionally preserves explicit grouping and uses compact postorder child indices. `bootstrap-ast-v1` defines the next source-oriented compiler boundary without introducing semantic resolution, types, ownership, capabilities, contracts, or backend behavior.

The Python implementation in `merit/bootstrap/ast_contract.py` is the initial independent oracle. The Merit-native compiler must later produce the same canonical data for the complete accepted alpha corpus before AST replacement is considered complete.

## Input

The input is a finite postorder sequence of:

```text
ExpressionNode {
    kind: i32,
    start: i64,
    length: i64,
    left: i64,
    right: i64,
}
```

Every child index must reference an earlier record. Source starts and lengths are non-negative byte values. Unknown kinds, forward references, and malformed atom children are contract violations rather than recoverable source diagnostics.

## Canonical node

The canonical representation is logically:

```text
AstNode {
    kind: String,
    start: i64,
    length: i64,
    children: [AstNode],
    grouping_origins: [(start: i64, length: i64)],
}
```

The implementation may use numeric enums or interned names internally, but canonical serialization uses the names defined here.

Supported names are:

- `identifier`
- `exact_numeric`
- `string`
- `invalid`
- `call`
- `field`
- `generic_apply`
- `sequence`
- `field_initializer`
- `constructor`
- `equal`
- `not_equal`
- `greater_equal`
- `less_equal`
- `greater`
- `less`
- `add`
- `subtract`
- `multiply`
- `divide`

## Group normalization

Parser kind `33` is an explicit parenthesized group. It does not survive as a semantic AST node. Lowering returns its child and appends the group source span to that child's `grouping_origins` sequence.

This rule makes grouping provenance available for diagnostics while preventing later semantic passes from treating redundant parentheses as language meaning.

## Child order

- atoms and invalid nodes have no children
- binary operators have left then right children
- field access has receiver then field identifier
- calls have callee followed by the optional argument or sequence root
- generic application has base followed by its type argument or sequence root
- sequence nodes have prefix then appended element
- field initializers have field identifier then value
- constructors have type expression followed by the optional initializer or sequence root

Child order is contractual and must not depend on map iteration, allocation identity, or backend traversal.

## Serialization

Canonical comparison uses compact JSON with:

- keys sorted lexicographically
- no insignificant whitespace
- recursive child order preserved
- `grouping_origins` omitted when empty
- no allocation addresses, object identities, generated binding IDs, or host-specific metadata

Source spans are included because differential compiler comparison must prove provenance equality, not merely semantic similarity.

## Corpus

`tests/project/bootstrap_corpus_v1.json` is the first manifest-driven corpus. A case declares a stable identifier, source or expression text, and the compiler stages that must agree. The manifest is append-only within `bootstrap-corpus-v1`; incompatible reinterpretation requires a new contract version.

The corpus runner verifies:

- independent Python reference output
- Python interpreter output
- generated native output
- canonical AST lowering for expression cases
- stable JSON serialization

Future Merit-native AST output must be added as another comparison source rather than replacing the Python oracle.

## Non-goals

This contract does not define:

- trivia-preserving CST records
- symbol resolution
- type checking
- numeric conversions
- ownership or destruction
- contracts or capabilities
- HIR or MIR
- parser error recovery policy beyond existing expression records
- optimization

Those remain later versioned gates.
