import pytest

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.mir_cfg_parity import NativeCfgRecord as R, lower_native_cfg_records
from merit.bootstrap.mir_contract import MirContractError

I64 = HirType("i64")
BOOL = HirType("bool")
UNIT = HirType("unit")


def _module(nodes, bindings=()):
    return HirModule("cfg", tuple(bindings), tuple(nodes), (nodes[-1].node_id,))


def _assert_cfg_parity(reference, records):
    fn = reference.functions[0]
    instructions = {block.block_id: block.instructions for block in fn.blocks}
    assert lower_native_cfg_records(records, instructions_by_block=instructions) == fn.blocks


def test_if_else_cfg_matches_canonical_hir_to_mir():
    nodes = [
        HirNode(0, "literal", BOOL, value=True),
        HirNode(1, "block", UNIT), HirNode(2, "block", UNIT),
        HirNode(3, "if", UNIT, children=(0, 1, 2)),
        HirNode(4, "return", UNIT),
        HirNode(5, "function", UNIT, children=(3, 4), symbol="choose"),
    ]
    ref = lower_hir_to_mir(_module(nodes))
    _assert_cfg_parity(ref, [
        R(10, 0, ordinal=0), R(10, 1, ordinal=1), R(10, 2, ordinal=2), R(10, 3, ordinal=3),
        R(12, 0, operand=0, target_a=1, target_b=2),
        R(11, 1, target_a=3), R(11, 2, target_a=3), R(15, 3),
    ])


def test_if_without_else_preserves_explicit_false_block():
    nodes = [HirNode(0, "literal", BOOL, value=False), HirNode(1, "block", UNIT),
             HirNode(2, "if", UNIT, children=(0, 1)), HirNode(3, "return", UNIT),
             HirNode(4, "function", UNIT, children=(2, 3), symbol="optional")]
    ref = lower_hir_to_mir(_module(nodes))
    _assert_cfg_parity(ref, [
        R(10,0,ordinal=0),R(10,1,ordinal=1),R(10,2,ordinal=2),R(10,3,ordinal=3),
        R(12,0,operand=0,target_a=1,target_b=2),R(11,1,target_a=3),R(11,2,target_a=3),R(15,3)
    ])


def test_while_cfg_matches_re_evaluated_condition_shape():
    binding = HirBinding(0, "keep", BOOL, mutable=True)
    nodes = [HirNode(0,"identifier",BOOL,binding_id=0), HirNode(1,"block",UNIT),
             HirNode(2,"while",UNIT,children=(0,1)), HirNode(3,"return",UNIT),
             HirNode(4,"function",UNIT,children=(2,3),symbol="loop")]
    ref = lower_hir_to_mir(_module(nodes, (binding,)))
    _assert_cfg_parity(ref, [
        R(10,0,ordinal=0),R(10,1,ordinal=1),R(10,2,ordinal=2),R(10,3,ordinal=3),
        R(11,0,target_a=1),R(12,1,operand=0,target_a=2,target_b=3),R(11,2,target_a=1),R(15,3)
    ])


def test_integer_match_cfg_preserves_case_order_and_default_last():
    binding = HirBinding(0,"code",I64)
    nodes = [HirNode(0,"identifier",I64,binding_id=0), HirNode(1,"block",UNIT),
             HirNode(2,"match_arm",UNIT,children=(1,),value=10), HirNode(3,"block",UNIT),
             HirNode(4,"match_arm",UNIT,children=(3,),value=20), HirNode(5,"block",UNIT),
             HirNode(6,"match_arm",UNIT,children=(5,),value=None),
             HirNode(7,"match",UNIT,children=(0,2,4,6)), HirNode(8,"return",UNIT),
             HirNode(9,"function",UNIT,children=(7,8),symbol="dispatch")]
    ref = lower_hir_to_mir(_module(nodes,(binding,)))
    _assert_cfg_parity(ref, [
        R(10,0,ordinal=0),R(10,1,ordinal=1),R(10,2,ordinal=2),R(10,3,ordinal=3),R(10,4,ordinal=4),
        R(13,0,operand=0,target_a=1,case_value=10,ordinal=0),
        R(13,0,operand=0,target_a=2,case_value=20,ordinal=1),
        R(14,0,operand=0,target_a=3,ordinal=2),
        R(11,1,target_a=4),R(11,2,target_a=4),R(11,3,target_a=4),R(15,4)
    ])


@pytest.mark.parametrize("records, message", [
    ([R(10,0,ordinal=0),R(10,0,ordinal=1),R(15,0)], "unique"),
    ([R(10,0,ordinal=1),R(15,0)], "ordinals"),
    ([R(10,0,ordinal=0),R(11,0,target_a=9)], "unknown block"),
    ([R(10,0,ordinal=0),R(15,0),R(11,0,target_a=0)], "multiple terminators"),
    ([R(10,0,ordinal=0),R(13,0,operand=0,target_a=0,case_value=1,ordinal=0)], "default"),
    ([R(10,0,ordinal=0),R(13,0,operand=0,target_a=0,case_value=1,ordinal=0),R(13,0,operand=0,target_a=0,case_value=1,ordinal=1),R(14,0,operand=0,target_a=0,ordinal=2)], "duplicate"),
])
def test_malformed_native_cfg_is_rejected(records, message):
    with pytest.raises(MirContractError, match=message):
        lower_native_cfg_records(records)
