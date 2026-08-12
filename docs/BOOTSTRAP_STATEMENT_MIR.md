# Bootstrap statement to structured MIR bridge

`bootstrap_mir_statement_lowering` is the source-backed bridge between the measured native statement/expression front end and the structured whole-function MIR walker.

## Input boundary

The bridge consumes only native replacement records and source structures that already have independent parity gates:

- `Token`
- `StatementRecord`
- `StatementOperand`
- expression-span AST records
- resolved expression HIR records

Python does not supply block IDs, event nesting, instruction placement, condition locals, or return locals.

## Decisions owned natively

For the supported statement slice, Merit-native code owns:

1. source binding/local identity for `let` and `var`;
2. root-first expression temporary allocation;
3. postorder global MIR instruction numbering;
4. binding-initialization copy placement;
5. `if` / `else` / `end_if` nesting from real token/block structure;
6. `while` / `end_while` nesting and loop-body boundaries;
7. condition operand locals derived from native expression HIR;
8. return operand locals derived from native expression HIR;
9. the `MirLowerEvent` stream consumed directly by `lower_structured_mir`.

The structured walker then independently owns deterministic block allocation, branch/jump topology, loop back-edges, block-local instruction ordinals, and explicit returns.

## Supported source statements

This milestone supports:

- `let`
- `var`
- `return`
- `if` with or without `else`
- `while`

The integration gate covers a real source function containing a binding initializer, nested `if -> while`, a loop-body return, an else-branch return, and a final join return. Interpreter and generated-native output must agree exactly on both the emitted event stream and the resulting CFG/placement records.

## Explicit remaining boundary

The bridge rejects unsupported statement effects with stable `100 + statement_kind` status values rather than falling back to Python inference:

- `print`
- `drop`
- `match`
- `with capability`
- `replace`

Those operations require their effect, ownership, cleanup, and/or arm semantics to become explicit native MIR records before they can be admitted to this replacement boundary.

## Next replacement slice

The next coherent milestone is ownership-aware statement MIR: native `drop`, owned moves/replacement, cleanup on return and control-flow exits, and exact once-only destruction across branch/loop joins. After cleanup semantics are explicit, extend the source-backed control walker through match arms and capability/effect statements.
