import pytest

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.mir_cfg_parity import NativeCfgRecord as C
from merit.bootstrap.mir_cfg_placement import NativeInstructionPlacement as P, lower_native_cfg_function
from merit.bootstrap.mir_contract import MirContractError

I64 = HirType("i64")
BOOL = HirType("bool")
UNIT = HirType("unit")


def _module(nodes, bindings=()):
    return HirModule("placed", tuple(bindings), tuple(nodes), (nodes[-1].node_id,))


def _assert_whole_function_parity(reference, cfg, placements):
    function = reference.functions[0]
    instructions = tuple(instruction for block in function.blocks for instruction in block.instructions)
    rebuilt = lower_native_cfg_function(
        module_name=reference.name,
        function_name=function.name,
        return_type=function.return_type,
        locals=function.locals,
        instructions=instructions,
        cfg_records=cfg,
        placements=placements,
        entry_block=function.entry_block,
        capabilities=function.capabilities,
    )
    assert rebuilt == reference


def test_if_else_places_branch_mutations_in_native_blocks():
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
    reference = lower_hir_to_mir(_module(nodes, (binding,)))
    cfg = [
        C(10,0,ordinal=0), C(10,1,ordinal=1), C(10,2,ordinal=2), C(10,3,ordinal=3),
        C(12,0,operand=1,target_a=1,target_b=2),
        C(11,1,target_a=3), C(11,2,target_a=3), C(15,3,operand=0),
    ]
    placements = [P(0,0,0), P(1,1,0), P(1,2,1), P(2,3,0), P(2,4,1)]
    _assert_whole_function_parity(reference, cfg, placements)


def test_while_places_mutation_only_in_body_and_preserves_back_edge():
    binding = HirBinding(0, "keep", BOOL, mutable=True)
    nodes = [
        HirNode(0, "identifier", BOOL, binding_id=0),
        HirNode(1, "literal", BOOL, value=False),
        HirNode(2, "assign", BOOL, children=(1,), binding_id=0),
        HirNode(3, "block", UNIT, children=(2,)),
        HirNode(4, "while", UNIT, children=(0, 3)),
        HirNode(5, "return", UNIT),
        HirNode(6, "function", UNIT, children=(4, 5), symbol="loop_once"),
    ]
    reference = lower_hir_to_mir(_module(nodes, (binding,)))
    cfg = [
        C(10,0,ordinal=0), C(10,1,ordinal=1), C(10,2,ordinal=2), C(10,3,ordinal=3),
        C(11,0,target_a=1), C(12,1,operand=0,target_a=2,target_b=3),
        C(11,2,target_a=1), C(15,3),
    ]
    placements = [P(2,0,0), P(2,1,1)]
    _assert_whole_function_parity(reference, cfg, placements)


def test_match_places_each_arm_instruction_stream_without_reordering():
    binding = HirBinding(0, "code", I64, mutable=True)
    nodes = [
        HirNode(0, "identifier", I64, binding_id=0),
        HirNode(1, "literal", I64, value=11), HirNode(2, "assign", I64, children=(1,), binding_id=0),
        HirNode(3, "block", UNIT, children=(2,)), HirNode(4, "match_arm", UNIT, children=(3,), value=10),
        HirNode(5, "literal", I64, value=22), HirNode(6, "assign", I64, children=(5,), binding_id=0),
        HirNode(7, "block", UNIT, children=(6,)), HirNode(8, "match_arm", UNIT, children=(7,), value=20),
        HirNode(9, "literal", I64, value=33), HirNode(10, "assign", I64, children=(9,), binding_id=0),
        HirNode(11, "block", UNIT, children=(10,)), HirNode(12, "match_arm", UNIT, children=(11,), value=None),
        HirNode(13, "match", UNIT, children=(0,4,8,12)),
        HirNode(14, "identifier", I64, binding_id=0), HirNode(15, "return", I64, children=(14,)),
        HirNode(16, "function", I64, children=(13,15), symbol="dispatch"),
    ]
    reference = lower_hir_to_mir(_module(nodes, (binding,)))
    cfg = [
        C(10,0,ordinal=0), C(10,1,ordinal=1), C(10,2,ordinal=2), C(10,3,ordinal=3), C(10,4,ordinal=4),
        C(13,0,operand=0,target_a=1,case_value=10,ordinal=0),
        C(13,0,operand=0,target_a=2,case_value=20,ordinal=1),
        C(14,0,operand=0,target_a=3,ordinal=2),
        C(11,1,target_a=4), C(11,2,target_a=4), C(11,3,target_a=4), C(15,4,operand=0),
    ]
    placements = [P(1,0,0),P(1,1,1),P(2,2,0),P(2,3,1),P(3,4,0),P(3,5,1)]
    _assert_whole_function_parity(reference, cfg, placements)


def test_terminated_if_arm_does_not_receive_synthetic_join_jump():
    nodes = [
        HirNode(0, "literal", BOOL, value=True),
        HirNode(1, "literal", I64, value=7), HirNode(2, "return", I64, children=(1,)),
        HirNode(3, "block", UNIT, children=(2,)), HirNode(4, "block", UNIT),
        HirNode(5, "if", UNIT, children=(0,3,4)), HirNode(6, "return", UNIT),
        HirNode(7, "function", UNIT, children=(5,6), symbol="early"),
    ]
    reference = lower_hir_to_mir(_module(nodes))
    function = reference.functions[0]
    cfg = [
        C(10,0,ordinal=0), C(10,1,ordinal=1), C(10,2,ordinal=2), C(10,3,ordinal=3),
        C(12,0,operand=0,target_a=1,target_b=2), C(15,1,operand=1),
        C(11,2,target_a=3), C(15,3),
    ]
    placements = [P(0,0,0), P(1,1,0)]
    _assert_whole_function_parity(reference, cfg, placements)
    assert function.blocks[1].terminator.kind == "return"


@pytest.mark.parametrize("placements,message", [
    ([P(0,0,0), P(0,0,1)], "more than once"),
    ([], "unplaced"),
    ([P(0,0,1)], "ordinals"),
    ([P(9,0,0)], "unknown block"),
])
def test_invalid_native_instruction_placement_is_rejected(placements, message):
    instruction = lower_hir_to_mir(_module([
        HirNode(0,"literal",I64,value=1), HirNode(1,"return",I64,children=(0,)),
        HirNode(2,"function",I64,children=(1,),symbol="one")
    ])).functions[0]
    flat = tuple(i for b in instruction.blocks for i in b.instructions)
    cfg = [C(10,0,ordinal=0), C(15,0,operand=0)]
    with pytest.raises(MirContractError, match=message):
        lower_native_cfg_function(
            module_name="placed", function_name="one", return_type=instruction.return_type,
            locals=instruction.locals, instructions=flat, cfg_records=cfg, placements=placements,
        )
