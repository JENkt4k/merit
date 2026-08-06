# HIR parameter to MIR ABI lowering

This slice connects checked `bootstrap-hir-v1` function parameters to the
versioned `bootstrap-mir-abi-v1` scalar calling convention.

## Pipeline

```text
checked HIR function + leading parameter nodes
→ parameter/binding validation
→ executable HIR with declarations removed
→ bootstrap-mir-v1 lowering
→ derived bootstrap-mir-abi-v1 signatures
→ deterministic scalar C ABI
```

## Parameter representation

A function parameter is represented by a leading HIR `parameter` child whose
`binding_id` resolves to a `HirBinding`. Parameter nodes are declarations and
are removed before executable statement lowering.

The parameter node, binding, MIR local, and ABI parameter must agree on:

- semantic binding identity;
- type;
- ownership mode;
- mutability.

Parameter order is the order of leading parameter nodes in the function, not
binding-ID order and not map iteration order. MIR local IDs continue to follow
the deterministic core lowering rule: binding-backed locals are allocated in
ascending semantic binding-ID order.

## Call validation

Before MIR construction, every HIR call is checked against the callee's derived
parameter list:

- the callee must be a function in the same HIR module;
- argument count must match exactly;
- argument and parameter types must match exactly;
- owned parameters require an owned or moved argument;
- borrowed parameters require borrow-compatible arguments;
- mutable-borrow parameters require a mutable-borrow argument.

The ordinary HIR-to-MIR lowerer then preserves source argument order in the MIR
call operand list. The ABI C emitter preserves that order again in the emitted
call expression.

## Export policy

Exported C names are explicit policy supplied to `lower_hir_to_mir_abi`.
They are not inferred from parser spelling or embedded accidentally in MIR.
Unknown export-policy function names are rejected.

## Current supported slice

The end-to-end executable path supports scalar `i64`, `bool`, and `unit`
functions, checked scalar arithmetic, structured control flow, and calls with
ordered scalar arguments.

## Deferred work

- aggregate and exact-decimal parameters;
- concrete pointer representation for borrows;
- exact-once cleanup across call edges;
- cross-module symbol resolution and linkage;
- public header generation and symbol versioning;
- integration with the Merit-native parser and semantic checker.
