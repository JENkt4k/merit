# Bootstrap Cleanup C Contract

`bootstrap-cleanup-c-v1` is the first backend boundary that consumes the ownership proof produced by `bootstrap-mir-ownership-v1`.

```text
validated MIR ABI
→ ownership transfer analysis
→ deterministic cleanup actions
→ explicit destructor calls in C
```

## Core rule

Every owned value must have exactly one terminal action on every supported path:

- transfer to an owned callee parameter;
- transfer through an owned return value;
- explicit destruction in MIR; or
- implicit cleanup on a return edge.

The cleanup emitter does not infer destructors from C types. The caller supplies an explicit `CleanupCPolicy` mapping each owned MIR type requiring cleanup to one stable C destructor symbol.

## Return-edge cleanup

The ownership analyzer provides cleanup actions per return block. The C emitter materializes these calls immediately before the corresponding return, preserving the analyzer's deterministic order.

A returned owned operand is absent from the cleanup list because ownership transfers to the caller.

## Calls

Call argument transfer semantics remain defined by `bootstrap-mir-ownership-v1`:

| ABI parameter | Caller effect |
|---|---|
| `value` | copy |
| `owned` | move |
| `borrowed` | immutable borrow |
| `mutable_borrow` | mutable borrow |

When an owned argument is moved to a callee, the caller does not destroy it. The callee either transfers it onward, returns it, explicitly destroys it, or runs its own return-edge cleanup.

## Destructor policy

Destructor bindings are versioned and canonical:

```python
CleanupCPolicy((
    DestructorBinding(MirType("i64"), "destroy_i64"),
))
```

The policy rejects:

- duplicate type bindings;
- duplicate destructor symbols;
- symbols that are not already valid C identifiers;
- symbols that collide with emitted Merit functions;
- missing bindings for any type used by a cleanup action.

## Determinism

The emitter preserves:

- module function order;
- block order;
- instruction order;
- ownership-plan cleanup order;
- stable destructor symbol selection;
- canonical policy serialization.

It emits no timestamps, paths, addresses, or host-dependent identifiers.

## Current scope

The executable cleanup subset currently proves exact-once cleanup for scalar resource handles represented by supported MIR scalar types. This is sufficient to test ownership transfer and destruction ordering without inventing an aggregate ABI.

Deferred work:

- explicit MIR cleanup blocks rather than direct backend materialization;
- materializing explicit `drop` and `deallocate` through typed destructor bindings;
- loop fixed-point ownership analysis;
- typed-error and unwind cleanup edges;
- aggregate and exact-decimal resource layouts;
- concrete borrow pointer representation;
- cross-module destructor summaries;
- public header generation for destructor symbols.
