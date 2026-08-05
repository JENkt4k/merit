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

## Adoption sequence

1. Lower one primitive expression slice from AST to HIR in both compilers.
2. Serialize both artifacts with `canonical_hir_json()`.
3. Feed them into the parity engine from `merit.bootstrap.parity`.
4. Expand vertically through decimals, contracts, structures, ownership, generics, capabilities, and the ledger application.
5. Do not lower to MIR until the corresponding HIR slice is semantically checked and parity-tested.

The contract may be extended only through a new version when an incompatible semantic distinction is required.