# Bootstrap MIR Scalar Parameter ABI

`bootstrap-mir-abi-v1` adds explicit scalar function signatures to the stable
`bootstrap-mir-v1` graph without changing that graph's serialization.

## Boundary

The ABI layer defines:

- one signature for every MIR function;
- ordered parameters;
- the MIR local bound to each parameter at function entry;
- parameter type, ownership, and mutability;
- an optional stable exported C name.

The underlying MIR still owns control flow, instruction order, temporaries,
contracts, capabilities, drops, and numeric policies.

## Parameter binding

Each parameter references an existing MIR local. The ABI validator requires the
parameter's type, ownership mode, and mutability to exactly match that local.
This avoids creating a second semantic representation of function inputs.

Parameters are ordered. Call operands are transferred in the same order:

```text
signature: (left -> local 0, right -> local 1)
call operands: (local 7, local 8)
C call: function(m7, m8)
entry bindings: m0 = p0; m1 = p1;
```

No backend reordering is permitted.

## Supported scalar ABI

The first executable slice supports:

- `i64` parameters;
- `bool` parameters;
- any number of scalar parameters;
- scalar or `unit` returns;
- forward calls;
- optional explicit exported C names;
- checked arithmetic inside callees.

## Ownership

The ABI records `value`, `owned`, `borrowed`, and `mutable_borrow` parameter
modes. The current scalar C emitter validates and preserves the metadata but
only scalar value representation is executable. Pointer/aggregate lowering and
borrow enforcement remain deferred.

## Stable names

An explicit `exported_name` controls the C prototype, definition, and all calls.
Distinct Merit functions that sanitize to the same C identifier are rejected.
This is an early stable-symbol boundary, not yet the complete public C ABI.

## Rejection rules

Emission fails when:

- signatures do not exactly cover module functions;
- a parameter references an unknown local;
- parameter metadata disagrees with its local;
- call arity differs from the signature;
- a value-returning call has no result;
- a `unit` call has a result;
- exported names collide after C sanitization;
- parameter or return types are outside the scalar backend subset.

## Deferred work

- HIR function-parameter lowering into this ABI;
- aggregate and decimal parameters;
- pointer representation for borrows;
- ownership transfer and cleanup across calls;
- cross-module declarations and linkage;
- public visibility and symbol-version policy;
- ABI verification against generated headers.
