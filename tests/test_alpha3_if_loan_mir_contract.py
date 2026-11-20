"""Strict v3 MIR join proof, independent of a producer."""

from dataclasses import replace

import pytest

from merit.bootstrap.mir_contract import (
    MirBlock, MirContractError, MirFunction, MirInstruction, MirLocal,
    MirLocalLoanEffect, MirModule, MirTerminator, MirType, SourceSpan,
    canonical_mir_json, load_mir_json, parse_mir,
)


def if_loan_module() -> MirModule:
    i32 = MirType("i32")
    locals_ = (
        MirLocal(0, "owner", i32, source_binding_id=10),
        MirLocal(1, "view", i32, ownership="local_reference", source_binding_id=11),
        MirLocal(2, "condition", i32),
        MirLocal(3, "read", i32),
    )
    blocks = (
        MirBlock(0, (MirInstruction(0, "borrow", result=1, operands=(0,)),
                     MirInstruction(1, "const", result=2, value=1)),
                 MirTerminator("branch", operands=(2,), targets=(1, 2))),
        MirBlock(1, (MirInstruction(2, "copy", result=3, operands=(1,)),),
                 MirTerminator("jump", targets=(3,))),
        MirBlock(2, (MirInstruction(3, "nop"),),
                 MirTerminator("jump", targets=(3,))),
        MirBlock(3, (MirInstruction(4, "nop"),), MirTerminator("return")),
    )
    span = SourceSpan(10, 8)
    effects = (
        MirLocalLoanEffect("create", 0, 11, 10, span),
        MirLocalLoanEffect("use", 2, 11, 10, span),
        MirLocalLoanEffect("end", 4, 11, 10, span, join_block_id=3),
    )
    return MirModule("rm2", (MirFunction("main", i32, locals_, blocks, 0,
                                       local_loan_effects=effects),),
                     "bootstrap-mir-v3")


def test_v3_join_round_trip_and_old_reader_rejection() -> None:
    module = if_loan_module()
    assert load_mir_json(canonical_mir_json(module)) == module
    data = module.to_data()
    data["schema"] = "bootstrap-mir-v2"
    with pytest.raises(MirContractError):
        parse_mir(data)


@pytest.mark.parametrize("change", [
    lambda data: data["functions"][0]["local_loan_effects"][-1].pop("join_block_id"),
    lambda data: data["functions"][0]["local_loan_effects"][-1].update(join_block_id=2),
    lambda data: data["functions"][0]["blocks"][2]["terminator"].update(targets=[1]),
    lambda data: data["functions"][0]["blocks"][1]["instructions"].append(
        MirInstruction(5, "drop", operands=(0,)).to_data()),
])
def test_v3_rejects_missing_end_wrong_join_wrong_edge_and_owner_drop(change) -> None:
    data = if_loan_module().to_data()
    change(data)
    with pytest.raises(MirContractError):
        parse_mir(data)
