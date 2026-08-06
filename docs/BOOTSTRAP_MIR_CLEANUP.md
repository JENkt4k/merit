# Bootstrap MIR Cleanup Materialization

`bootstrap-mir-cleanup-v1` moves destruction semantics out of backend inference and into explicit MIR instructions.

## Pipeline

```text
validated bootstrap-mir-abi-v1
→ bootstrap-mir-ownership-v1 proof
→ typed destructor policy
→ explicit drop/deallocate instructions
→ deterministic C emission
```

## Guarantees

- Every implicit return cleanup action becomes an ordered MIR `drop` instruction.
- Existing explicit `drop` and `deallocate` instructions receive a validated destructor symbol.
- Owned return operands are transferred and are not destroyed in the callee.
- Owned call arguments are moved; the caller does not receive an implicit cleanup instruction.
- Borrowed arguments remain owned by the caller and are cleaned up on caller exit.
- Instruction IDs are renumbered deterministically in function, block, and source order.
- A supplied ownership plan must exactly equal a freshly computed plan.
- Missing destructor bindings, non-owned drops, and symbol collisions fail closed.

## Destructor policy

A destructor is selected by full `MirType`, not by C spelling or source name. Destructor symbols must already be valid C identifiers and may not collide with emitted Merit functions.

## Backend boundary

The materialized C emitter does not consult ownership liveness while emitting a function. It executes explicit symbol-bearing cleanup instructions in MIR order. This makes cleanup visible to differential comparison, later optimization validation, and stage equivalence.

## Deferred

- loop ownership fixed points and loop cleanup edges
- typed-error and unwind cleanup
- aggregate and decimal resource ABIs
- concrete borrow pointer representation
- cross-module destructor summaries
- optimizer proofs that preserve exact-once cleanup
