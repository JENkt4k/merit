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

Typed string literals use the existing `const` instruction. Their exact quoted
source spelling is retained as the constant value, the resolved `string` type is
carried by the result local, and their numeric policy is `none`.

Field HIR lowers to `load_field` with one explicit receiver local and one resolved
field symbol. Calls and constructors carry resolved symbols and ordered operand
locals; symbol names are not value bindings and do not consume local IDs.

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

## Measured expression boundary

The executable Merit-native MIR boundary covers eleven expression-corpus cases
once this branch passes its hosted gate. The measured surface includes:

- exact/checked numeric constants and arithmetic
- resolved source bindings
- typed comparisons
- structural grouping aliases
- typed non-numeric string constants
- resolved ordinary calls, including empty and ordered multi-argument calls
- nested calls
- typed field loads
- aggregate construction with declaration-ordered operands
- call/constructor/field composition

Two native record families are intentionally used. The original primitive record
remains frozen for arithmetic, bindings, comparisons, groups, and strings. The
additive composite record carries resolved symbol spans and explicit ordered
operand markers for calls and construction, plus receiver identity for field
loads. Both record streams preserve root-first temporary allocation while
emitting instructions postorder.

The native path owns:

- source-binding local identity
- root-first temporary-local allocation
- postorder instruction emission
- operand-local references and call/constructor operand order
- resolved call, constructor, and field symbol identity
- binary operator identity
- explicit numeric policy
- resolved result type codes
- source spans and canonical HIR provenance

Python adapters validate and serialize those already-made decisions; they do not
re-run HIR-to-MIR lowering or infer symbols/operands from expression spelling.
The repository gates compare canonical output against the Python
`lower_hir_to_mir` oracle and independently require Merit interpreter/native
record equality.

### Remaining expression gap

`identity<i64>(1)` remains outside measured MIR parity. HIR correctly preserves
its generic argument, but `bootstrap-mir-v1` call instructions currently carry
only the resolved callee symbol and operand locals. Promoting that case before
MIR gains explicit specialization metadata would certify an information-losing
boundary. The next expression-MIR contract revision should preserve generic
specialization identity directly rather than reconstructing it from source.

## Non-goals

This contract does not:

- define C syntax or ABI spelling
- optimize control flow
- choose register allocation
- add LLVM
- define async, concurrency, networking, or package behavior
- claim that all compiler paths emit Merit-native MIR yet

## Adoption sequence

1. Lower checked HIR into canonical `bootstrap-mir-v1` in the Python oracle.
2. Emit measured expression MIR from the Merit-native compiler.
3. Require exact interpreter/native agreement in the shared parity engine.
4. Complete generic-call MIR identity, then close the expression corpus at 12/12.
5. Expand vertically through statements, contracts, control flow, ownership,
   capabilities, modules, and the acceptance applications.
6. Make deterministic C emission consume replacement MIR only.
7. Remove the Python compiler from the trusted production path after whole-pipeline
   differential replacement is proven.
