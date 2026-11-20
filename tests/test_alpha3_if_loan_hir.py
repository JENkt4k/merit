"""Versioned source-to-HIR boundary for bounded RM2 if loans."""

from dataclasses import replace

import pytest

from merit.bootstrap.hir_contract import (
    HirContractError, canonical_hir_json, load_hir_json,
)
from merit.bootstrap.local_borrow_source_hir import lower_checked_local_borrow_source_hir


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
