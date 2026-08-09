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
- explicit numeric policy for arithmetic
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

Merit's primitive integer arithmetic is checked, so the first executable `i64` HIR slice emits `checked` for binary arithmetic. Exact numeric literal nodes retain the literal spelling and use the `exact` numeric policy.

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

## Executable primitive expression slice

The first measured HIR slice covers the repository corpus cases `precedence-product` (`1+2*3`) and `explicit-group` (`(1+2)*3`). They are deliberately self-contained numeric expressions so the first gate can verify typed HIR without pretending unresolved identifiers already have binding semantics.

The typed boundary supplies resolved type `i64`. `merit.bootstrap.hir_expression.lower_primitive_expression_hir` independently lowers the canonical Python AST into `bootstrap-hir-v1`. `bootstrap_hir.lower_primitive_hir_records` performs the corresponding lowering in Merit and emits flat `HirExpressionRecord` data for interpreter/native comparison.

The native flat contract uses:

- kind `1`: exact numeric literal
- kind `2`: primitive binary arithmetic
- kind `3`: grouping alias to an earlier native record
- type code `1`: `i64`
- numeric policy `1`: exact
- numeric policy `2`: checked

Grouping aliases exist only to bridge parser record indexing. `merit.bootstrap.hir_parity` collapses them before canonical HIR construction, so parentheses do not create semantic HIR nodes or perturb canonical node IDs.

`tests/project/test_bootstrap_hir_parity_gate.py` runs one temporary Merit probe over every corpus case marked `hir`, captures both interpreted and native record streams, reconstructs canonical HIR, and requires the shared parity engine to report complete HIR parity. Interpreter/native record equality is an independent requirement.

## Adoption sequence

1. **Complete:** lower the first primitive typed expression slice from AST to HIR in both compilers.
2. **Complete:** serialize and compare both artifacts through the shared parity engine.
3. Expand the typed expression slice through identifiers/bindings and comparisons once semantic binding/type information is available at the replacement boundary.
4. Expand vertically through decimals, contracts, structures, ownership, generics, capabilities, and the ledger application.
5. Do not claim a later HIR slice until its semantic inputs are checked and parity-tested.
6. Do not lower new semantic coverage to MIR until the corresponding HIR slice is stable.

The contract may be extended only through a new version when an incompatible semantic distinction is required.
