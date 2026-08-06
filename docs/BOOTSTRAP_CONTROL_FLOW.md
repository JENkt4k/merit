# Bootstrap control-flow lowering

This document defines the first structured control-flow slice from
`bootstrap-hir-v1` into `bootstrap-mir-v1`.

## Supported shapes

### If

An `if` HIR node contains:

1. a boolean value node
2. a `block` node for the true path
3. an optional `block` node for the false path

Lowering creates an explicit `branch` terminator, deterministic true and false
blocks, and a join block. Missing `else` branches become an explicit empty false
block rather than backend fallthrough.

### While

A `while` HIR node contains:

1. a condition value node
2. a body `block` node

Lowering creates entry, condition, body, and exit structure. The condition is
located in its own MIR block so it is operationally reevaluated on every loop
iteration. The body ends in an explicit jump to the condition block when it
does not terminate.

### Match

The initial match slice supports integer cases plus exactly one default arm.
A `match` node contains a value followed by `match_arm` nodes. Each arm contains
one `block`. Integer arm values become switch cases; a null arm value denotes
the default.

Lowering creates a `switch` terminator whose case order follows HIR arm order.
The default target is always last. Duplicate integer cases, multiple defaults,
and missing defaults are rejected.

## Determinism

- block IDs are allocated in lowering order
- instruction IDs remain globally increasing within a function
- branch target order is true then false
- switch target order follows source arm order, then default
- implicit paths use explicit jumps
- no C fallthrough or expression evaluation order defines Merit behavior

## Rejection boundary

Malformed shapes are rejected with deterministic `HirToMirError` diagnostics.
The lowerer does not infer missing blocks, synthesize a match default, reorder
cases, or reinterpret non-integer patterns.

## Deferred work

This slice does not yet include:

- value-producing control-flow expressions and phi-like joins
- break and continue
- pattern destructuring
- cleanup-edge insertion for owned values
- exception or typed-error unwinding
- MIR-to-C emission

Those features must preserve the explicit block and terminator model introduced
here rather than reintroducing backend-defined sequencing.
