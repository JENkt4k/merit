# Bootstrap HIR v1

`bootstrap-hir-v1` is Merit's backend-neutral semantic interchange contract between typed AST lowering and MIR construction.

It exists so the Python reference compiler and Merit-native bootstrap compiler can be compared using canonical semantic artifacts rather than implementation-specific objects or formatted debug output.

## Required properties

HIR must preserve:

- unique semantic binding IDs
- resolved types and generic type arguments
- deterministic postorder node references
- source provenance
- ownership mode at binding and operation boundaries
- explicit numeric policy for arithmetic and typed comparisons
- explicit conversion policy for conversions
- capability requirements on sensitive operations and scopes
- contracts as explicit semantic nodes

HIR must not contain:

- parser token records
- Python object identities
- allocation addresses
- C syntax or evaluation-order assumptions
- implicit lossy numeric conversions
- backend-specific cleanup reconstruction

## Canonical form

`canonical_hir_json()` emits compact, key-sorted JSON. Both compiler implementations must produce equivalent canonical documents for corpus cases marked with the `hir` stage.

Node IDs and binding IDs are part of the comparison contract. They must be assigned deterministically from source traversal and semantic binding creation, not memory allocation order.

## Numeric policies

Binary operations require one of:

- `exact`
- `checked`
- `wrapping`
- `saturating`
- `floating`

Conversions require one of:

- `exact`
- `checked`
- `round`
- `truncate`
- `reinterpret`

`none` is permitted only for nodes where the policy is not applicable.

Merit's primitive integer arithmetic is checked, so executable `i64` arithmetic HIR emits `checked`. Exact numeric literal nodes retain the literal spelling and use the `exact` numeric policy. Integer comparisons are exact semantic operations: their operands are resolved `i64`, their result type is `bool`, and their binary node uses `exact` rather than inheriting the arithmetic overflow policy.

## Ownership modes

The v1 interchange recognizes:

- `value`
- `owned`
- `borrowed`
- `mutable_borrow`
- `moved`
- `none`

This is semantic metadata, not a substitute for the ownership checker. The checker must validate transitions and then emit the accepted mode into HIR.

## Graph rules

Nodes use deterministic postorder references: every child ID must be lower than its parent ID. This provides stable serialization, makes cycles impossible in valid lowered expressions, and simplifies differential comparison.

Roots identify top-level semantic declarations or executable units. Every root, child, and binding reference must resolve inside the module.

## Executable expression slices

The first measured slice covered `precedence-product` (`1+2*3`) and `explicit-group` (`(1+2)*3`) with an explicitly supplied `i64` destination type.

The second measured slice added `left-associative-subtract` (`a-b-c`), `comparison-last` (`a==b+1`), and `division-before-addition` (`a/2+4`). The test boundary supplies an ordered resolved environment in which fixture identifiers are `i64`. That order defines canonical binding IDs on the reference side. The Merit-native probe independently assigns the same IDs by first occurrence of unique identifier source text, using byte-for-byte span comparison rather than Python-side name resolution.

The third measured slice adds `empty-call` (`f()`), `argument-sequence` (`f(1,2+3)`), `field-before-addition` (`account.balance+1`), and `nested-call-field` (`f(g(1)).value`). Semantic resolution remains explicit at the replacement boundary:

- function signatures provide resolved callable symbols, ordered parameter types, and result types;
- field signatures provide the resolved receiver type, field symbol, and result type;
- value bindings continue to receive deterministic dense binding IDs;
- callee identifiers and field-name identifiers are semantic symbols, not value bindings, and therefore do not consume binding IDs;
- argument-sequence parser nodes are structural only and flatten into ordered call operands;
- field HIR contains only the receiver value as a child and carries the resolved field symbol on the field node;
- call HIR contains only argument values as children and carries the resolved callable symbol on the call node.

`merit.bootstrap.hir_expression.lower_resolved_expression_hir` lowers the canonical Python AST using these explicit semantic environments. The Merit bootstrap project emits flat `HirExpressionRecord` data containing resolved binding IDs, operand/result types, operator codes, source spans, structural symbol/sequence records, and numeric policies. `merit.bootstrap.hir_parity` validates and reconstructs canonical HIR before differential comparison.

The native flat contract uses:

- kind `1`: exact numeric literal
- kind `2`: primitive integer arithmetic
- kind `3`: grouping alias to an earlier native record
- kind `4`: resolved value identifier
- kind `5`: typed comparison
- kind `6`: resolved call; the left record identifies the callable symbol and the optional right record supplies arguments
- kind `7`: resolved field; the left record is the receiver and the right record identifies the field symbol
- kind `8`: structural argument sequence, flattened during canonical reconstruction
- kind `9`: non-value symbol reference for call/field names
- type code `0`: structural/no value
- type code `1`: `i64`
- type code `2`: `bool`
- additional positive type codes: explicitly supplied resolved fixture types such as `Account` and `Record`
- numeric policy `0`: none
- numeric policy `1`: exact
- numeric policy `2`: checked

Arithmetic operator codes `1..4` are `+`, `-`, `*`, `/`. Comparison operator codes `5..10` are `==`, `!=`, `>=`, `<=`, `>`, `<`.

Grouping aliases exist only to bridge parser record indexing. `merit.bootstrap.hir_parity` collapses them before canonical HIR construction, so parentheses do not create semantic HIR nodes or perturb canonical node IDs. Structural argument-sequence and symbol-reference records are likewise removed before canonical HIR is constructed.

`tests/project/test_bootstrap_hir_parity_gate.py` runs one temporary Merit probe over every corpus case marked `hir`, captures both interpreted and native record streams, reconstructs canonical HIR, and requires the shared parity engine to report complete HIR parity. Interpreter/native record equality is an independent requirement.

When this call/field slice is green, measured executable HIR parity is 9/12 expression corpus cases. The remaining three cases require distinct semantic work rather than more of the same resolver surface: string literals, direct aggregate construction, and generic application/call resolution.

## Adoption sequence

1. **Complete:** lower primitive numeric expressions from AST to HIR in both compilers.
2. **Complete:** serialize and compare those artifacts through the shared parity engine.
3. **Complete:** resolve simple identifier bindings, preserve deterministic binding IDs, and type comparison results as `bool`.
4. **Complete when this slice is green:** resolve ordinary calls and field accesses from explicit semantic inputs and raise measured HIR parity to 9/12.
5. Add aggregate construction only after constructor/type/field identities are explicit at the replacement boundary.
6. Add generic application/calls only after generic symbol and type-argument resolution is explicit.
7. Add non-numeric literal typing without weakening exact-literal semantics.
8. Expand vertically through decimals, contracts, structures, ownership, generics, capabilities, and the ledger application.
9. Do not claim a later HIR slice until its semantic inputs are checked and parity-tested.
10. Do not lower new semantic coverage to MIR until the corresponding HIR slice is stable.

The contract may be extended only through a new version when an incompatible semantic distinction is required.
