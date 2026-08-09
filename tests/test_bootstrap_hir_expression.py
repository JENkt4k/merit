from __future__ import annotations

import pytest

from merit.bootstrap.ast_contract import AstNode
from merit.bootstrap.hir_contract import HirType, canonical_hir_json
from merit.bootstrap.hir_expression import (
    PrimitiveHirLoweringError,
    lower_primitive_expression_hir,
)
from merit.bootstrap.hir_parity import (
    NativeHirContractError,
    lower_native_primitive_hir_records,
)


I64 = HirType("i64")


def _precedence_ast() -> AstNode:
    one = AstNode("exact_numeric", 0, 1)
    two = AstNode("exact_numeric", 2, 1)
    three = AstNode("exact_numeric", 4, 1)
    product = AstNode("multiply", 2, 3, (two, three))
    return AstNode("add", 0, 5, (one, product))


def test_reference_primitive_hir_is_typed_postorder_and_checked():
    hir = lower_primitive_expression_hir(
        _precedence_ast(), "1+2*3", expected_type=I64, module_name="precedence-product"
    )
    assert hir.roots == (4,)
    assert [node.kind for node in hir.nodes] == ["literal", "literal", "literal", "binary", "binary"]
    assert [node.value for node in hir.nodes[:3]] == ["1", "2", "3"]
    assert hir.nodes[3].children == (1, 2)
    assert hir.nodes[3].symbol == "*"
    assert hir.nodes[3].numeric_policy == "checked"
    assert hir.nodes[4].children == (0, 3)
    assert hir.nodes[4].symbol == "+"
    assert all(node.type == I64 for node in hir.nodes)


def test_native_records_reconstruct_same_canonical_hir():
    records = [
        (1, 0, 1, -1, -1, 0, 1, 1),
        (1, 2, 1, -1, -1, 0, 1, 1),
        (1, 4, 1, -1, -1, 0, 1, 1),
        (2, 2, 3, 1, 2, 3, 1, 2),
        (2, 0, 5, 0, 3, 1, 1, 2),
    ]
    native = lower_native_primitive_hir_records(records, "1+2*3", module_name="precedence-product")
    reference = lower_primitive_expression_hir(
        _precedence_ast(), "1+2*3", expected_type=I64, module_name="precedence-product"
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


def test_native_group_alias_disappears_without_changing_semantic_ids():
    # Native parser records retain the parenthesized group at index 3, while
    # canonical HIR must contain only the three literals and two binaries.
    records = [
        (1, 1, 1, -1, -1, 0, 1, 1),
        (1, 3, 1, -1, -1, 0, 1, 1),
        (2, 1, 3, 0, 1, 1, 1, 2),
        (3, 0, 5, 2, -1, 0, 1, 0),
        (1, 6, 1, -1, -1, 0, 1, 1),
        (2, 0, 7, 3, 4, 3, 1, 2),
    ]
    hir = lower_native_primitive_hir_records(records, "(1+2)*3")
    assert len(hir.nodes) == 5
    assert hir.roots == (4,)
    assert hir.nodes[3].kind == "literal"
    assert hir.nodes[4].children == (2, 3)


@pytest.mark.parametrize(
    "records,message",
    [
        ([], "empty"),
        ([(0, 0, 1, -1, -1, 0, 1, 0)], "unsupported kind"),
        ([(1, -1, 1, -1, -1, 0, 1, 1)], "span"),
        ([(1, 0, 1, 0, -1, 0, 1, 1)], "invalid child"),
        ([(1, 0, 1, -1, -1, 0, 2, 1)], "type code"),
        ([(1, 0, 1, -1, -1, 0, 1, 2)], "exact policy"),
        ([(3, 0, 1, 0, -1, 0, 1, 0)], "non-postorder child"),
    ],
)
def test_malformed_native_hir_is_rejected(records, message):
    with pytest.raises(NativeHirContractError, match=message):
        lower_native_primitive_hir_records(records, "1")


def test_reference_rejects_untyped_or_unsupported_ast_shapes():
    with pytest.raises(PrimitiveHirLoweringError, match="outside primitive"):
        lower_primitive_expression_hir(
            AstNode("identifier", 0, 1), "x", expected_type=I64
        )
    with pytest.raises(PrimitiveHirLoweringError, match="outside source"):
        lower_primitive_expression_hir(
            AstNode("exact_numeric", 3, 1), "1", expected_type=I64
        )
