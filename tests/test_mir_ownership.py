import pytest

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature, MirParameter
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
)
from merit.bootstrap.mir_ownership import (
    MirOwnershipError,
    analyze_ownership,
    canonical_ownership_json,
)

I64 = MirType("i64")
UNIT = MirType("unit")


def local(local_id, name, ownership="value"):
    return MirLocal(local_id, name, I64, ownership=ownership)


def function(name, locals_, blocks, return_type=I64):
    return MirFunction(name, return_type, tuple(locals_), tuple(blocks), 0)


def abi(functions, signatures):
    return MirAbiModule(MirModule("ownership", tuple(functions)), tuple(signatures))


def signature(name, parameters=()):
    return MirFunctionSignature(name, tuple(parameters))


def parameter(name, local_id, ownership="value"):
    return MirParameter(name, local_id, I64, ownership)


def test_owned_parameter_is_live_and_return_transfers_it():
    fn = function(
        "identity",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return", operands=(0,)))],
    )
    plan = analyze_ownership(abi([fn], [signature("identity", [parameter("item", 0, "owned")])]))
    assert plan.functions[0].cleanup_actions == ()
    assert plan.functions[0].exit_live_owned == ((0, ()),)


def test_unreturned_owned_parameter_is_cleaned_up():
    fn = function(
        "discard",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    plan = analyze_ownership(abi([fn], [signature("discard", [parameter("item", 0, "owned")])]))
    cleanup = plan.functions[0].cleanup_actions
    assert [(item.block_id, item.local_id, item.order) for item in cleanup] == [(0, 0, 0)]


def test_cleanup_order_is_reverse_local_order():
    fn = function(
        "discard_two",
        [local(0, "a", "owned"), local(1, "b", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    plan = analyze_ownership(abi([
        fn
    ], [signature("discard_two", [parameter("a", 0, "owned"), parameter("b", 1, "owned")])]))
    assert [item.local_id for item in plan.functions[0].cleanup_actions] == [1, 0]


def test_owned_call_argument_is_recorded_as_move():
    consume = function(
        "consume",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    caller = function(
        "caller",
        [local(0, "item", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="consume"),), MirTerminator("return"))],
        UNIT,
    )
    plan = analyze_ownership(abi(
        [caller, consume],
        [signature("caller", [parameter("item", 0, "owned")]), signature("consume", [parameter("item", 0, "owned")])],
    ))
    caller_plan = plan.functions[0]
    assert [(item.local_id, item.mode) for item in caller_plan.call_transfers] == [(0, "move")]
    assert caller_plan.cleanup_actions == ()


def test_borrowed_call_keeps_owned_argument_live_for_cleanup():
    inspect = function(
        "inspect",
        [local(0, "item", "borrowed")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    caller = function(
        "caller",
        [local(0, "item", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="inspect"),), MirTerminator("return"))],
        UNIT,
    )
    plan = analyze_ownership(abi(
        [caller, inspect],
        [signature("caller", [parameter("item", 0, "owned")]), signature("inspect", [parameter("item", 0, "borrowed")])],
    ))
    assert plan.functions[0].call_transfers[0].mode == "borrow"
    assert [item.local_id for item in plan.functions[0].cleanup_actions] == [0]


def test_mutable_borrow_mode_is_explicit():
    edit = function(
        "edit",
        [MirLocal(0, "item", I64, mutable=True, ownership="mutable_borrow")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    caller = function(
        "caller",
        [local(0, "item", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="edit"),), MirTerminator("return"))],
        UNIT,
    )
    plan = analyze_ownership(abi(
        [caller, edit],
        [signature("caller", [parameter("item", 0, "owned")]), signature("edit", [MirParameter("item", 0, I64, "mutable_borrow", True)])],
    ))
    assert plan.functions[0].call_transfers[0].mode == "mutable_borrow"


def test_value_call_parameter_is_copy():
    read = function("read", [local(0, "x")], [MirBlock(0, (), MirTerminator("return", operands=(0,)))])
    caller = function(
        "caller",
        [local(0, "x")],
        [MirBlock(0, (MirInstruction(0, "call", result=0, operands=(0,), symbol="read"),), MirTerminator("return", operands=(0,)))],
    )
    plan = analyze_ownership(abi(
        [caller, read],
        [signature("caller"), signature("read", [parameter("x", 0)])],
    ))
    assert plan.functions[0].call_transfers[0].mode == "copy"


def test_explicit_drop_prevents_exit_cleanup():
    fn = function(
        "drop_it",
        [local(0, "item", "owned")],
        [MirBlock(0, (MirInstruction(0, "drop", operands=(0,)),), MirTerminator("return"))],
        UNIT,
    )
    plan = analyze_ownership(abi([fn], [signature("drop_it", [parameter("item", 0, "owned")])]))
    assert plan.functions[0].cleanup_actions == ()


def test_double_drop_is_rejected():
    fn = function(
        "bad",
        [local(0, "item", "owned")],
        [MirBlock(0, (
            MirInstruction(0, "drop", operands=(0,)),
            MirInstruction(1, "drop", operands=(0,)),
        ), MirTerminator("return"))],
        UNIT,
    )
    with pytest.raises(MirOwnershipError, match="non-live owned local"):
        analyze_ownership(abi([fn], [signature("bad", [parameter("item", 0, "owned")])]))


def test_use_after_move_is_rejected():
    fn = function(
        "bad",
        [local(0, "item", "owned"), local(1, "moved", "owned")],
        [MirBlock(0, (
            MirInstruction(0, "move", result=1, operands=(0,)),
            MirInstruction(1, "borrow", result=0, operands=(0,)),
        ), MirTerminator("return"))],
        UNIT,
    )
    with pytest.raises(MirOwnershipError, match="non-live owned local"):
        analyze_ownership(abi([fn], [signature("bad", [parameter("item", 0, "owned")])]))


def test_copy_into_owned_local_is_rejected():
    fn = function(
        "bad",
        [local(0, "item", "owned"), local(1, "other", "owned")],
        [MirBlock(0, (MirInstruction(0, "copy", result=1, operands=(0,)),), MirTerminator("return"))],
        UNIT,
    )
    with pytest.raises(MirOwnershipError, match="copies into owned local"):
        analyze_ownership(abi([fn], [signature("bad", [parameter("item", 0, "owned")])]))


def test_call_move_requires_owned_local():
    consume = function("consume", [local(0, "x", "owned")], [MirBlock(0, (), MirTerminator("return"))], UNIT)
    caller = function(
        "caller",
        [local(0, "x")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="consume"),), MirTerminator("return"))],
        UNIT,
    )
    with pytest.raises(MirOwnershipError, match="requires move ownership"):
        analyze_ownership(abi(
            [caller, consume],
            [signature("caller"), signature("consume", [parameter("x", 0, "owned")])],
        ))


def test_unknown_call_signature_is_rejected():
    fn = function(
        "caller",
        [local(0, "x")],
        [MirBlock(0, (MirInstruction(0, "call", result=0, symbol="missing"),), MirTerminator("return", operands=(0,)))],
    )
    with pytest.raises(MirOwnershipError, match="unknown signature"):
        analyze_ownership(abi([fn], [signature("caller")]))


def test_call_arity_disagreement_is_rejected():
    callee = function("callee", [local(0, "x")], [MirBlock(0, (), MirTerminator("return", operands=(0,)))])
    caller = function("caller", [local(0, "x")], [MirBlock(0, (MirInstruction(0, "call", result=0, symbol="callee"),), MirTerminator("return", operands=(0,)))])
    with pytest.raises(MirOwnershipError, match="arity disagrees"):
        analyze_ownership(abi([caller, callee], [signature("caller"), signature("callee", [parameter("x", 0)])]))


def test_equal_branch_states_join_successfully():
    blocks = (
        MirBlock(0, (), MirTerminator("branch", operands=(1,), targets=(1, 2))),
        MirBlock(1, (), MirTerminator("jump", targets=(3,))),
        MirBlock(2, (), MirTerminator("jump", targets=(3,))),
        MirBlock(3, (), MirTerminator("return")),
    )
    fn = function("branch", [local(0, "item", "owned"), local(1, "condition")], blocks, UNIT)
    plan = analyze_ownership(abi([fn], [signature("branch", [parameter("item", 0, "owned")])]))
    assert [item.local_id for item in plan.functions[0].cleanup_actions] == [0]


def test_inconsistent_branch_states_are_rejected():
    blocks = (
        MirBlock(0, (), MirTerminator("branch", operands=(1,), targets=(1, 2))),
        MirBlock(1, (MirInstruction(0, "drop", operands=(0,)),), MirTerminator("jump", targets=(3,))),
        MirBlock(2, (), MirTerminator("jump", targets=(3,))),
        MirBlock(3, (), MirTerminator("return")),
    )
    fn = function("branch", [local(0, "item", "owned"), local(1, "condition")], blocks, UNIT)
    with pytest.raises(MirOwnershipError, match="inconsistent ownership states"):
        analyze_ownership(abi([fn], [signature("branch", [parameter("item", 0, "owned")])]))


def test_loops_fail_closed_until_loop_cleanup_is_defined():
    blocks = (
        MirBlock(0, (), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (), MirTerminator("branch", operands=(0,), targets=(1, 2))),
        MirBlock(2, (), MirTerminator("return")),
    )
    fn = function("loop", [local(0, "condition")], blocks, UNIT)
    with pytest.raises(MirOwnershipError, match="control-flow cycle"):
        analyze_ownership(abi([fn], [signature("loop")]))


def test_canonical_plan_is_deterministic():
    fn = function(
        "discard",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    module = abi([fn], [signature("discard", [parameter("item", 0, "owned")])])
    assert canonical_ownership_json(analyze_ownership(module)) == canonical_ownership_json(analyze_ownership(module))


def test_multiple_return_blocks_get_independent_cleanup_actions():
    blocks = (
        MirBlock(0, (), MirTerminator("branch", operands=(1,), targets=(1, 2))),
        MirBlock(1, (), MirTerminator("return")),
        MirBlock(2, (), MirTerminator("return")),
    )
    fn = function("returns", [local(0, "item", "owned"), local(1, "condition")], blocks, UNIT)
    plan = analyze_ownership(abi([fn], [signature("returns", [parameter("item", 0, "owned")])]))
    assert [(item.block_id, item.local_id) for item in plan.functions[0].cleanup_actions] == [(1, 0), (2, 0)]
