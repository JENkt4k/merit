"""Versioned source-to-HIR boundary for bounded RM2 if loans."""

from dataclasses import replace

import pytest

from merit.bootstrap.hir_contract import (
    HirContractError, canonical_hir_json, load_hir_json,
)
from merit.bootstrap.local_borrow_source_hir import lower_checked_local_borrow_source_hir
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.mir_contract import canonical_mir_json, load_mir_json


SOURCE = (
    "module rm2\nfn main()->i32 { var x:i32=1; "
    "let r: borrow i32 = borrow x; "
    "if 1 { print(r); } else { print(0); } "
    "x=2; return 0; }"
)


def test_checked_if_source_produces_deterministic_hir_v3() -> None:
    hir = lower_checked_local_borrow_source_hir(SOURCE)
    assert hir.schema == "bootstrap-hir-v3"
    assert len(hir.local_loans) == 1
    assert [node.kind for node in hir.nodes].count("if") == 1
    assert load_hir_json(canonical_hir_json(hir)) == hir
    assert canonical_hir_json(lower_checked_local_borrow_source_hir(SOURCE)) == canonical_hir_json(hir)


def test_checked_if_source_produces_join_anchored_mir_v3() -> None:
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(SOURCE))
    assert mir.schema == "bootstrap-mir-v3"
    function = mir.functions[0]
    assert len(function.blocks) == 4
    assert [effect.kind for effect in function.local_loan_effects] == ["create", "use", "end"]
    assert function.local_loan_effects[-1].join_block_id == function.blocks[3].block_id
    assert load_mir_json(canonical_mir_json(mir)) == mir


@pytest.mark.parametrize("arms", [
    "if 1 { print(r); } else { print(r); }",
    "if 1 { inspect(r); } else { print(0); }",
])
def test_join_effect_is_stable_for_either_arm_use(arms: str) -> None:
    source=("module rm2\nfn inspect(borrow value:i32)->i32 { return value; }\n"
            "fn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; "
            f"{arms} x=2; return 0; }}")
    hir = lower_checked_local_borrow_source_hir(source)
    mir = lower_hir_to_mir(hir)
    assert mir.schema == "bootstrap-mir-v3"
    assert mir.functions[0].local_loan_effects[-1].join_block_id == 3
    assert load_mir_json(canonical_mir_json(mir)) == mir


def test_hir_v2_reader_rejects_if_loan_semantics() -> None:
    hir = lower_checked_local_borrow_source_hir(SOURCE)
    with pytest.raises(HirContractError, match="straight-line"):
        replace(hir, schema="bootstrap-hir-v2")
    with pytest.raises(HirContractError, match="straight-line"):
        load_hir_json(canonical_hir_json(hir).replace("bootstrap-hir-v3", "bootstrap-hir-v2"))


def test_hir_v3_reader_rejects_missing_branch_arm_and_orphan_node() -> None:
    hir = lower_checked_local_borrow_source_hir(SOURCE)
    branch = next(node for node in hir.nodes if node.kind == "if")
    broken = tuple(replace(node, children=node.children[:2]) if node.node_id == branch.node_id
                   else node for node in hir.nodes)
    with pytest.raises(HirContractError, match="two explicit arm blocks"):
        replace(hir, nodes=broken)
    with pytest.raises(HirContractError, match="unreachable semantic nodes"):
        replace(hir, roots=())
