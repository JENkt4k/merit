# Bootstrap MIR v1

`bootstrap-mir-v1` is Merit's backend-neutral operational interchange format.
It sits after typed HIR and semantic checking, and before deterministic C
emission:

```text
AST -> typed HIR -> semantic checks -> MIR -> ordered C
```

The purpose of MIR is to ensure the C backend translates already-defined Merit
semantics instead of inventing them through C expression ordering, implicit
conversions, temporary lifetimes, or cleanup behavior.

## Core invariants

- Each function has explicit locals, basic blocks, and one entry block.
- Every basic block ends in exactly one terminator.
- Instructions are linearly ordered within each block.
- Branches, jumps, and switches reference explicit block IDs.
- All blocks must be reachable from the entry block.
- Local, block, instruction, and function identities are deterministic.
- Arithmetic and conversion behavior is explicit.
- Ownership transfers, borrows, drops, allocation, and deallocation are explicit.
- Contracts and capability checks are explicit instructions.
- Source spans remain available for diagnostics.
- Serialization is compact, canonical JSON suitable for differential comparison.

## Instructions

The v1 instruction set includes:

- constants, copies, moves, and borrows
- field loads and stores
- binary arithmetic
- conversions
- calls and construction
- contract and capability checks
- allocation and deallocation
- deterministic drops
- no-op markers for retained source boundaries

MIR does not contain implicit evaluation. Operands are local IDs, so a backend
must emit each instruction in the order recorded by its block.

## Terminators

Supported terminators are:

- `return`
- `jump`
- `branch`
- `switch`
- `unreachable`

A branch has one condition and exactly two targets. A switch has one selector,
one target per case value, and one final default target.

## Numerics

Binary instructions require one of:

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

`none` is allowed only for instructions where that policy is irrelevant.

## Ownership and resources

Locals preserve ownership mode and may retain the HIR binding ID from which they
were lowered. Resource-sensitive operations are represented directly:

- `move`
- `borrow`
- `drop`
- `allocate`
- `deallocate`

This makes exact-once destruction and explicit allocation properties available
to parity tests before C is generated.

## Contracts and capabilities

`contract_check` instructions identify preconditions, postconditions, or
invariants. `capability_check` instructions list the exact capabilities being
required. Functions also record their complete declared capability set.

## Non-goals

This contract does not:

- define C syntax or ABI spelling
- optimize control flow
- choose register allocation
- add LLVM
- define async, concurrency, networking, or package behavior
- claim that the Merit-native compiler emits MIR yet

## Adoption sequence

1. Lower a small checked HIR slice into `bootstrap-mir-v1` in the Python oracle.
2. Emit the same canonical MIR from the Merit-native compiler.
3. Add `mir` observations to the existing parity engine.
4. Reach exact MIR parity for primitive, decimal, contract, ownership, and
   capability examples.
5. Make deterministic C emission consume MIR only.
6. Expand vertically until all nine acceptance projects pass through the new
   pipeline.
