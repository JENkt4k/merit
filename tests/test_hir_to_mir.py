import json

import pytest

from merit.bootstrap.hir_contract import (
    HirBinding,
    HirModule,
    HirNode,
    HirType,
    SourceSpan,
)
from merit.bootstrap.hir_to_mir import HirToMirError, lower_hir_to_mir
from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir


I64 = HirType("i64")
BOOL = HirType("bool")
UNIT = HirType("unit")


def module(nodes, *, bindings=(), roots=None, name="example"):
    if roots is None:
        roots = (nodes[-1].node_id,)
    return HirModule(name, tuple(bindings), tuple(nodes), tuple(roots))


def test_lowers_exact_binary_return_in_deterministic_order():
    nodes = [
        HirNode(0, "literal", I64, value=2, span=SourceSpan(0, 1)),
        HirNode(1, "literal", I64, value=3, span=SourceSpan(4, 1)),
        HirNode(2, "binary", I64, children=(0, 1), symbol="+", numeric_policy="exact"),
        HirNode(3, "return", I64, children=(2,)),
        HirNode(4, "function", I64, children=(3,), symbol="add"),
    ]
    mir = lower_hir_to_mir(module(nodes))
    function = mir.functions[0]
    assert function.name == "add"
    assert [item.kind for item in function.blocks[0].instructions] == ["const", "const", "binary"]
    assert function.blocks[0].instructions[2].numeric_policy == "exact"
    assert function.blocks[0].terminator.kind == "return"
    assert len(function.blocks[0].terminator.operands) == 1


def test_canonical_mir_round_trip_is_stable():
    nodes = [
        HirNode(0, "literal", I64, value=7),
        HirNode(1, "return", I64, children=(0,)),
        HirNode(2, "function", I64, children=(1,), symbol="seven"),
    ]
    lowered = lower_hir_to_mir(module(nodes))
    encoded = canonical_mir_json(lowered)
    assert canonical_mir_json(parse_mir(json.loads(encoded))) == encoded


def test_binding_ids_become_stable_source_local_ids():
    bindings = (
        HirBinding(7, "amount", I64, mutable=True, ownership="value"),
        HirBinding(12, "result", I64, ownership="owned"),
    )
    nodes = [
        HirNode(0, "literal", I64, value=9),
        HirNode(1, "let", I64, children=(0,), binding_id=7),
        HirNode(2, "identifier", I64, binding_id=7),
        HirNode(3, "return", I64, children=(2,)),
        HirNode(4, "function", I64, children=(1, 3), symbol="binding_demo"),
    ]
    function = lower_hir_to_mir(module(nodes, bindings=bindings)).functions[0]
    source_ids = [local.source_binding_id for local in function.locals[:2]]
    assert source_ids == [7, 12]
    assert function.locals[0].mutable is True
    assert function.locals[1].ownership == "owned"
    assert function.blocks[0].instructions[1].operands == (2,)


def test_checked_conversion_preserves_policy():
    nodes = [
        HirNode(0, "literal", I64, value=4),
        HirNode(1, "conversion", HirType("Decimal", (I64,)), children=(0,), conversion_policy="checked"),
        HirNode(2, "return", HirType("Decimal", (I64,)), children=(1,)),
        HirNode(3, "function", HirType("Decimal", (I64,)), children=(2,), symbol="convert"),
    ]
    instruction = lower_hir_to_mir(module(nodes)).functions[0].blocks[0].instructions[1]
    assert instruction.kind == "convert"
    assert instruction.conversion_policy == "checked"


def test_call_constructor_move_and_borrow_are_ordered():
    binding = HirBinding(0, "item", I64, ownership="owned")
    nodes = [
        HirNode(0, "identifier", I64, binding_id=0, ownership="owned"),
        HirNode(1, "borrow", I64, children=(0,), binding_id=0, ownership="borrowed"),
        HirNode(2, "call", I64, children=(1,), symbol="inspect"),
        HirNode(3, "constructor", HirType("Box", (I64,)), children=(2,), symbol="Box", ownership="owned"),
        HirNode(4, "move", HirType("Box", (I64,)), children=(3,), binding_id=0, ownership="moved"),
        HirNode(5, "return", HirType("Box", (I64,)), children=(4,)),
        HirNode(6, "function", HirType("Box", (I64,)), children=(5,), symbol="pipeline"),
    ]
    instructions = lower_hir_to_mir(module(nodes, bindings=(binding,))).functions[0].blocks[0].instructions
    assert [item.kind for item in instructions] == ["borrow", "call", "construct", "move"]
    assert [item.instruction_id for item in instructions] == [0, 1, 2, 3]


def test_contract_and_capability_semantics_are_explicit():
    nodes = [
        HirNode(0, "literal", BOOL, value=True),
        HirNode(1, "contract_check", UNIT, children=(0,), symbol="precondition"),
        HirNode(2, "capability_scope", UNIT, capabilities=("filesystem.read",), children=(1,)),
        HirNode(3, "return", UNIT),
        HirNode(4, "function", UNIT, children=(2, 3), symbol="read", capabilities=("filesystem.read",)),
    ]
    function = lower_hir_to_mir(module(nodes)).functions[0]
    instructions = function.blocks[0].instructions
    assert function.capabilities == ("filesystem.read",)
    assert instructions[0].kind == "capability_check"
    assert instructions[0].capabilities == ("filesystem.read",)
    assert instructions[2].kind == "contract_check"
    assert instructions[2].contract_kind == "precondition"


def test_drop_is_lowered_against_resolved_binding():
    binding = HirBinding(3, "resource", HirType("Resource"), ownership="owned")
    nodes = [
        HirNode(0, "drop", UNIT, binding_id=3, ownership="owned"),
        HirNode(1, "return", UNIT),
        HirNode(2, "function", UNIT, children=(0, 1), symbol="cleanup"),
    ]
    instruction = lower_hir_to_mir(module(nodes, bindings=(binding,))).functions[0].blocks[0].instructions[0]
    assert instruction.kind == "drop"
    assert instruction.operands == (0,)


def test_multiple_function_roots_preserve_root_order():
    nodes = [
        HirNode(0, "return", UNIT),
        HirNode(1, "function", UNIT, children=(0,), symbol="first"),
        HirNode(2, "return", UNIT),
        HirNode(3, "function", UNIT, children=(2,), symbol="second"),
    ]
    lowered = lower_hir_to_mir(module(nodes, roots=(1, 3)))
    assert [function.name for function in lowered.functions] == ["first", "second"]


@pytest.mark.parametrize(
    "nodes,message",
    [
        ([HirNode(0, "literal", I64, value=1)], "is not a function"),
        ([HirNode(0, "return", UNIT), HirNode(1, "function", UNIT, children=(0,))], "requires a symbol"),
        ([HirNode(0, "binary", I64, numeric_policy="exact"), HirNode(1, "return", I64, children=(0,)), HirNode(2, "function", I64, children=(1,), symbol="bad")], "requires two operands"),
        ([HirNode(0, "conversion", I64, conversion_policy="checked"), HirNode(1, "return", I64, children=(0,)), HirNode(2, "function", I64, children=(1,), symbol="bad")], "requires one operand"),
        ([HirNode(0, "call", I64), HirNode(1, "return", I64, children=(0,)), HirNode(2, "function", I64, children=(1,), symbol="bad")], "requires a resolved symbol"),
        ([HirNode(0, "constructor", I64), HirNode(1, "return", I64, children=(0,)), HirNode(2, "function", I64, children=(1,), symbol="bad")], "requires a type symbol"),
    ],
)
def test_invalid_core_shapes_fail_deterministically(nodes, message):
    with pytest.raises(HirToMirError, match=message):
        lower_hir_to_mir(module(nodes))


def test_malformed_if_fails_instead_of_approximating():
    nodes = [
        HirNode(0, "literal", BOOL, value=True),
        HirNode(1, "if", UNIT, children=(0,)),
        HirNode(2, "function", UNIT, children=(1,), symbol="branch"),
    ]
    with pytest.raises(HirToMirError, match="requires condition"):
        lower_hir_to_mir(module(nodes))


def test_statement_after_return_is_rejected():
    binding = HirBinding(0, "x", I64)
    nodes = [
        HirNode(0, "return", UNIT),
        HirNode(1, "drop", UNIT, binding_id=0),
        HirNode(2, "function", UNIT, children=(0, 1), symbol="bad_order"),
    ]
    with pytest.raises(HirToMirError, match="appears after a terminator"):
        lower_hir_to_mir(module(nodes, bindings=(binding,)))


def test_void_function_gets_deterministic_implicit_return():
    nodes = [HirNode(0, "function", UNIT, symbol="empty")]
    function = lower_hir_to_mir(module(nodes)).functions[0]
    assert function.blocks[0].terminator.kind == "return"
    assert function.blocks[0].terminator.operands == ()
