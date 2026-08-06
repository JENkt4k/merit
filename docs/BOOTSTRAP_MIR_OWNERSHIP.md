# Bootstrap MIR Ownership and Cleanup

`bootstrap-mir-ownership-v1` is the fail-closed semantic pass between validated
`bootstrap-mir-abi-v1` and C emission.

## Purpose

The core MIR contract records moves, borrows, drops, calls, locals, and explicit
control flow. The ownership pass turns that operational information into two
backend-consumable results:

1. an explicit transfer mode for every call argument;
2. a deterministic cleanup list for every return edge.

The C backend must not infer ownership from C types, parameter spelling, or
whether a local happens to be used after a call.

## Call transfer modes

| ABI parameter ownership | Transfer mode | Caller state |
|---|---|---|
| `value` | `copy` | unchanged |
| `owned` | `move` | argument becomes non-live |
| `borrowed` | `borrow` | owned argument remains live |
| `mutable_borrow` | `mutable_borrow` | owned argument remains live |

Every transfer is keyed by MIR instruction ID and argument index. This makes
argument evaluation and transfer order explicit and reproducible.

## Owned-local state

The pass tracks only locals whose MIR ownership is `owned`.

- owned parameters are live at function entry;
- `move` consumes its owned operand and may create a new owned result;
- `drop` and `deallocate` consume their owned operands;
- borrow operations require a live value but do not consume it;
- an owned call parameter consumes the caller operand;
- an owned return operand transfers out of the function;
- remaining live owned locals are cleaned up at the return edge.

Copying into an owned local is rejected because that would duplicate ownership.
Using a moved or dropped local is rejected.

## Cleanup ordering

Cleanup actions are emitted in reverse local-ID order. This is deterministic and
provides stack-like destruction for the current bootstrap subset.

Each return block receives its own ordered cleanup list. A future backend pass
will insert the corresponding typed destructor operations before the return.

## Control-flow joins

All incoming edges to a block must agree on the exact set of live owned locals.
A join where one path moved or dropped a value and another retained it is
rejected. Merit does not silently select one path's ownership interpretation.

## Current loop boundary

This phase accepts acyclic MIR control flow. Cycles are rejected until loop
fixed-point ownership and cleanup-edge rules are specified and tested. Existing
loop-capable MIR and C emission remain available for non-owned scalar programs;
this ownership pass is an additional gate for resource-bearing functions.

## Deferred work

- loop ownership fixed points;
- cleanup insertion into MIR blocks;
- typed destructor symbol selection;
- unwind/error cleanup edges;
- aggregate and decimal resource ABIs;
- concrete pointer representation for borrows;
- cross-module ownership summaries;
- native destruction counters attached to real resource types.

The pass deliberately produces a plan rather than mutating the stable
`bootstrap-mir-v1` interchange. That keeps ownership proof and backend emission
separate and independently comparable.
