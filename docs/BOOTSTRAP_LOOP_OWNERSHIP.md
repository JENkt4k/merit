# Bootstrap loop ownership fixed points

`bootstrap-mir-ownership-v2` extends ownership analysis to cyclic MIR control flow.

## Rule

Each basic block has one exact incoming set of live owned locals. Every predecessor, including back edges, must agree on that set. A loop converges when revisiting its header preserves the same ownership state.

This admits loops that:

- operate only on scalar values;
- borrow owned values without consuming them;
- call borrowed or value parameters;
- carry an owned value unchanged to a later exit;
- clean remaining owned values on loop exit.

It rejects loops that consume ownership on a back edge, including:

- dropping a loop-carried owned value;
- moving it into another local;
- passing it to an owned parameter;
- producing different live-owned sets on distinct predecessors.

These cases require a future explicit loop-carried ownership construct rather than an inferred approximation.

## Algorithm

1. Seed the entry block with live owned parameters.
2. Transfer ownership state through instructions in block order.
3. Propagate the resulting state to successors.
4. Require exact equality when a successor already has an incoming state.
5. Stop when all reachable blocks have stable states.
6. Generate deterministic return cleanup in reverse local order.

The resulting ownership plan retains the v1 interchange shape, allowing the explicit MIR cleanup materializer to consume it unchanged.

## Deferred

- loop-carried owned phi values;
- break and continue syntax lowering;
- per-iteration allocation and destruction;
- partial initialization inside loops;
- typed-error and unwind edges.
