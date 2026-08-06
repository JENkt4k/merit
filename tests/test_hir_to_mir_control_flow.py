import pytest

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType
from merit.bootstrap.hir_to_mir import HirToMirError, lower_hir_to_mir
from merit.bootstrap.mir_contract import canonical_mir_json


I64 = HirType("i64")
BOOL = HirType("bool")
UNIT = HirType("unit")


def module(nodes, *, bindings=(), root=None):
    if root is None:
        root = nodes[-1].node_id
    return HirModule("control", tuple(bindings), tuple(nodes), (root,))


def test_if_else_lowers_to_branch_and_deterministic_join():
    binding = HirBinding(0, "result", I64, mutable=True)
    nodes = [
        HirNode(0, "literal", BOOL, value=True),
        HirNode(1, "literal", I64, value=1),
        HirNode(2, "assign", I64, children=(1,), binding_id=0),
        HirNode(3, "block", UNIT, children=(2,)),
        HirNode(4, "literal", I64, value=2),
        HirNode(5, "assign", I64, children=(4,), binding_id=0),
        HirNode(6, "block", UNIT, children=(5,)),
        HirNode(7, "if", UNIT, children=(0, 3, 6)),
        HirNode(8, "identifier", I64, binding_id=0),
        HirNode(9, "return", I64, children=(8,)),
        HirNode(10, "function", I64, children=(7, 9), symbol="choose"),
    ]
    function = lower_hir_to_mir(module(nodes, bindings=(binding,))).functions[0]
    assert [block.block_id for block in function.blocks] == [0, 1, 2, 3]
    assert function.blocks[0].terminator.kind == "branch"
    assert function.blocks[0].terminator.targets == (1, 2)
    assert function.blocks[1].terminator.targets == (3,)
    assert function.blocks[2].terminator.targets == (3,)
    assert function.blocks[3].terminator.kind == "return"


def test_if_without_else_has_explicit_empty_false_path():
    nodes = [
        HirNode(0, "literal", BOOL, value=False),
        HirNode(1, "block", UNIT),
        HirNode(2, "if", UNIT, children=(0, 1)),
        HirNode(3, "return", UNIT),
        HirNode(4, "function", UNIT, children=(2, 3), symbol="optional"),
    ]
    function = lower_hir_to_mir(module(nodes)).functions[0]
    assert len(function.blocks) == 4
    assert function.blocks[2].instructions == ()
    assert function.blocks[2].terminator.kind == "jump"


def test_while_lowers_to_entry_condition_body_and_exit_blocks():
    binding = HirBinding(0, "keep_going", BOOL, mutable=True)
    nodes = [
        HirNode(0, "identifier", BOOL, binding_id=0),
        HirNode(1, "literal", BOOL, value=False),
        HirNode(2, "assign", BOOL, children=(1,), binding_id=0),
        HirNode(3, "block", UNIT, children=(2,)),
        HirNode(4, "while", UNIT, children=(0, 3)),
        HirNode(5, "return", UNIT),
        HirNode(6, "function", UNIT, children=(4, 5), symbol="loop_once"),
    ]
    function = lower_hir_to_mir(module(nodes, bindings=(binding,))).functions[0]
    assert [block.terminator.kind for block in function.blocks] == [
        "jump", "branch", "jump", "return"
    ]
    assert function.blocks[0].terminator.targets == (1,)
    assert function.blocks[1].terminator.targets == (2, 3)
    assert function.blocks[2].terminator.targets == (1,)


def test_integer_match_lowers_to_switch_with_default_last():
    binding = HirBinding(0, "code", I64)
    nodes = [
        HirNode(0, "identifier", I64, binding_id=0),
        HirNode(1, "block", UNIT),
        HirNode(2, "match_arm", UNIT, children=(1,), value=10),
        HirNode(3, "block", UNIT),
        HirNode(4, "match_arm", UNIT, children=(3,), value=20),
        HirNode(5, "block", UNIT),
        HirNode(6, "match_arm", UNIT, children=(5,), value=None),
        HirNode(7, "match", UNIT, children=(0, 2, 4, 6)),
        HirNode(8, "return", UNIT),
        HirNode(9, "function", UNIT, children=(7, 8), symbol="dispatch"),
    ]
    function = lower_hir_to_mir(module(nodes, bindings=(binding,))).functions[0]
    switch = function.blocks[0].terminator
    assert switch.kind == "switch"
    assert switch.cases == (10, 20)
    assert switch.targets == (1, 2, 3)
    assert function.blocks[4].terminator.kind == "return"


def test_control_flow_serialization_is_deterministic():
    nodes = [
        HirNode(0, "literal", BOOL, value=True),
        HirNode(1, "block", UNIT),
        HirNode(2, "if", UNIT, children=(0, 1)),
        HirNode(3, "return", UNIT),
        HirNode(4, "function", UNIT, children=(2, 3), symbol="stable"),
    ]
    first = canonical_mir_json(lower_hir_to_mir(module(nodes)))
    second = canonical_mir_json(lower_hir_to_mir(module(nodes)))
    assert first == second


@pytest.mark.parametrize(
    "nodes,message",
    [
        ([HirNode(0, "if", UNIT), HirNode(1, "function", UNIT, children=(0,), symbol="bad")], "requires condition"),
        ([HirNode(0, "literal", BOOL, value=True), HirNode(1, "literal", UNIT), HirNode(2, "if", UNIT, children=(0, 1)), HirNode(3, "function", UNIT, children=(2,), symbol="bad")], "branches must be block"),
        ([HirNode(0, "literal", BOOL, value=True), HirNode(1, "literal", UNIT), HirNode(2, "while", UNIT, children=(0, 1)), HirNode(3, "function", UNIT, children=(2,), symbol="bad")], "body must be a block"),
        ([HirNode(0, "literal", I64, value=1), HirNode(1, "block", UNIT), HirNode(2, "match_arm", UNIT, children=(1,), value=1), HirNode(3, "match", UNIT, children=(0, 2)), HirNode(4, "function", UNIT, children=(3,), symbol="bad")], "requires a default arm"),
    ],
)
def test_malformed_control_flow_is_rejected(nodes, message):
    with pytest.raises(HirToMirError, match=message):
        lower_hir_to_mir(module(nodes))


def test_duplicate_match_cases_are_rejected():
    binding = HirBinding(0, "value", I64)
    nodes = [
        HirNode(0, "identifier", I64, binding_id=0),
        HirNode(1, "block", UNIT),
        HirNode(2, "match_arm", UNIT, children=(1,), value=1),
        HirNode(3, "block", UNIT),
        HirNode(4, "match_arm", UNIT, children=(3,), value=1),
        HirNode(5, "block", UNIT),
        HirNode(6, "match_arm", UNIT, children=(5,), value=None),
        HirNode(7, "match", UNIT, children=(0, 2, 4, 6)),
        HirNode(8, "function", UNIT, children=(7,), symbol="bad"),
    ]
    with pytest.raises(HirToMirError, match="duplicate case values"):
        lower_hir_to_mir(module(nodes, bindings=(binding,)))
