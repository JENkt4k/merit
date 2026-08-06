import pytest

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature, MirParameter
from merit.bootstrap.mir_contract import MirBlock, MirFunction, MirInstruction, MirLocal, MirModule, MirTerminator, MirType
from merit.bootstrap.mir_ownership import MirOwnershipError
from merit.bootstrap.mir_ownership_fixedpoint import analyze_ownership_fixedpoint

I64 = MirType("i64")
BOOL = MirType("bool")
UNIT = MirType("unit")


def local(i, name, ownership="value", type_=I64):
    return MirLocal(i, name, type_, ownership=ownership)


def param(name, i, ownership="value", type_=I64):
    return MirParameter(name, i, type_, ownership)


def abi(functions, signatures):
    return MirAbiModule(MirModule("loops", tuple(functions)), tuple(signatures))


def test_scalar_loop_converges():
    fn = MirFunction("loop", UNIT, (local(0, "condition", type_=BOOL),), (
        MirBlock(0, (), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (), MirTerminator("branch", operands=(0,), targets=(2, 3))),
        MirBlock(2, (), MirTerminator("jump", targets=(1,))),
        MirBlock(3, (), MirTerminator("return")),
    ), 0)
    plan = analyze_ownership_fixedpoint(abi([fn], [MirFunctionSignature("loop")]))
    assert plan.functions[0].cleanup_actions == ()


def test_owned_value_survives_loop_and_cleans_on_exit():
    fn = MirFunction("loop_owned", UNIT, (local(0, "item", "owned"), local(1, "condition", type_=BOOL)), (
        MirBlock(0, (), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (), MirTerminator("branch", operands=(1,), targets=(2, 3))),
        MirBlock(2, (MirInstruction(0, "borrow", result=1, operands=(0,)),), MirTerminator("jump", targets=(1,))),
        MirBlock(3, (), MirTerminator("return")),
    ), 0)
    plan = analyze_ownership_fixedpoint(abi([fn], [MirFunctionSignature("loop_owned", (param("item", 0, "owned"),))]))
    assert [(x.block_id, x.local_id) for x in plan.functions[0].cleanup_actions] == [(3, 0)]


@pytest.mark.parametrize("kind", ["drop", "move"])
def test_consuming_owned_value_inside_loop_is_rejected(kind):
    instruction = MirInstruction(0, kind, result=1 if kind == "move" else None, operands=(0,))
    fn = MirFunction("bad", UNIT, (
        local(0, "item", "owned"), local(1, "moved", "owned"), local(2, "condition", type_=BOOL)
    ), (
        MirBlock(0, (), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (), MirTerminator("branch", operands=(2,), targets=(2, 3))),
        MirBlock(2, (instruction,), MirTerminator("jump", targets=(1,))),
        MirBlock(3, (), MirTerminator("return")),
    ), 0)
    with pytest.raises(MirOwnershipError, match="joins inconsistent ownership states"):
        analyze_ownership_fixedpoint(abi([fn], [MirFunctionSignature("bad", (param("item", 0, "owned"),))]))


def test_borrowed_call_inside_loop_preserves_owned_state():
    inspect = MirFunction("inspect", UNIT, (local(0, "item", "borrowed"),), (MirBlock(0, (), MirTerminator("return")),), 0)
    caller = MirFunction("caller", UNIT, (local(0, "item", "owned"), local(1, "condition", type_=BOOL)), (
        MirBlock(0, (), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (), MirTerminator("branch", operands=(1,), targets=(2, 3))),
        MirBlock(2, (MirInstruction(0, "call", operands=(0,), symbol="inspect"),), MirTerminator("jump", targets=(1,))),
        MirBlock(3, (), MirTerminator("return")),
    ), 0)
    plan = analyze_ownership_fixedpoint(abi(
        [caller, inspect],
        [MirFunctionSignature("caller", (param("item", 0, "owned"),)), MirFunctionSignature("inspect", (param("item", 0, "borrowed"),))],
    ))
    assert plan.functions[0].call_transfers[0].mode == "borrow"
    assert [(x.block_id, x.local_id) for x in plan.functions[0].cleanup_actions] == [(3, 0)]


def test_owned_call_move_inside_loop_is_rejected():
    consume = MirFunction("consume", UNIT, (local(0, "item", "owned"),), (MirBlock(0, (), MirTerminator("return")),), 0)
    caller = MirFunction("caller", UNIT, (local(0, "item", "owned"), local(1, "condition", type_=BOOL)), (
        MirBlock(0, (), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (), MirTerminator("branch", operands=(1,), targets=(2, 3))),
        MirBlock(2, (MirInstruction(0, "call", operands=(0,), symbol="consume"),), MirTerminator("jump", targets=(1,))),
        MirBlock(3, (), MirTerminator("return")),
    ), 0)
    with pytest.raises(MirOwnershipError, match="joins inconsistent ownership states"):
        analyze_ownership_fixedpoint(abi(
            [caller, consume],
            [MirFunctionSignature("caller", (param("item", 0, "owned"),)), MirFunctionSignature("consume", (param("item", 0, "owned"),))],
        ))
