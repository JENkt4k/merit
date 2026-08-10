from __future__ import annotations

import pytest

from merit.bootstrap.ast_contract import AstNode
from merit.bootstrap.hir_contract import HirType, canonical_hir_json
from merit.bootstrap.hir_expression import (
    PrimitiveHirLoweringError,
    lower_bound_expression_hir,
    lower_primitive_expression_hir,
)
from merit.bootstrap.hir_parity import (
    NativeHirContractError,
    lower_native_primitive_hir_records,
)


I64 = HirType("i64")
BOOL = HirType("bool")


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
        (1, 0, 1, -1, -1, 0, 1, 1, -1),
        (1, 2, 1, -1, -1, 0, 1, 1, -1),
        (1, 4, 1, -1, -1, 0, 1, 1, -1),
        (2, 2, 3, 1, 2, 3, 1, 2, -1),
        (2, 0, 5, 0, 3, 1, 1, 2, -1),
    ]
    native = lower_native_primitive_hir_records(records, "1+2*3", module_name="precedence-product")
    reference = lower_primitive_expression_hir(
        _precedence_ast(), "1+2*3", expected_type=I64, module_name="precedence-product"
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


def test_native_group_alias_disappears_without_changing_semantic_ids():
    records = [
        (1, 1, 1, -1, -1, 0, 1, 1, -1),
        (1, 3, 1, -1, -1, 0, 1, 1, -1),
        (2, 1, 3, 0, 1, 1, 1, 2, -1),
        (3, 0, 5, 2, -1, 0, 1, 0, -1),
        (1, 6, 1, -1, -1, 0, 1, 1, -1),
        (2, 0, 7, 3, 4, 3, 1, 2, -1),
    ]
    hir = lower_native_primitive_hir_records(records, "(1+2)*3")
    assert len(hir.nodes) == 5
    assert hir.roots == (4,)
    assert hir.nodes[3].kind == "literal"
    assert hir.nodes[4].children == (2, 3)


def test_bound_reference_assigns_stable_binding_ids_and_bool_comparison_type():
    a = AstNode("identifier", 0, 1)
    b = AstNode("identifier", 3, 1)
    one = AstNode("exact_numeric", 5, 1)
    add = AstNode("add", 3, 3, (b, one))
    root = AstNode("equal", 0, 6, (a, add))
    hir = lower_bound_expression_hir(
        root,
        "a==b+1",
        expected_type=I64,
        bindings=(("a", I64), ("b", I64)),
        module_name="comparison-last",
    )
    assert [(binding.binding_id, binding.name) for binding in hir.bindings] == [(0, "a"), (1, "b")]
    assert [node.kind for node in hir.nodes] == ["identifier", "identifier", "literal", "binary", "binary"]
    assert hir.nodes[0].binding_id == 0
    assert hir.nodes[1].binding_id == 1
    assert hir.nodes[3].type == I64
    assert hir.nodes[3].numeric_policy == "checked"
    assert hir.nodes[4].type == BOOL
    assert hir.nodes[4].symbol == "=="
    assert hir.nodes[4].numeric_policy == "exact"


def test_native_bound_records_match_reference_comparison_hir():
    records = [
        (4, 0, 1, -1, -1, 0, 1, 0, 0),
        (4, 3, 1, -1, -1, 0, 1, 0, 1),
        (1, 5, 1, -1, -1, 0, 1, 1, -1),
        (2, 3, 3, 1, 2, 1, 1, 2, -1),
        (5, 0, 6, 0, 3, 5, 2, 1, -1),
    ]
    native = lower_native_primitive_hir_records(records, "a==b+1", module_name="comparison-last")
    a = AstNode("identifier", 0, 1)
    b = AstNode("identifier", 3, 1)
    one = AstNode("exact_numeric", 5, 1)
    reference = lower_bound_expression_hir(
        AstNode("equal", 0, 6, (a, AstNode("add", 3, 3, (b, one)))),
        "a==b+1",
        expected_type=I64,
        bindings=(("a", I64), ("b", I64)),
        module_name="comparison-last",
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


@pytest.mark.parametrize(
    "records,message",
    [
        ([], "empty"),
        ([(0, 0, 1, -1, -1, 0, 1, 0, -1)], "unsupported kind"),
        ([(1, -1, 1, -1, -1, 0, 1, 1, -1)], "span"),
        ([(1, 0, 1, 0, -1, 0, 1, 1, -1)], "invalid child"),
        ([(1, 0, 1, -1, -1, 0, 2, 1, -1)], "type code"),
        ([(1, 0, 1, -1, -1, 0, 1, 2, -1)], "exact policy"),
        ([(3, 0, 1, 0, -1, 0, 1, 0, -1)], "non-postorder child"),
        ([(4, 0, 1, -1, -1, 0, 1, 0, -1)], "binding ID"),
        ([(5, 0, 1, -1, -1, 5, 2, 1, -1)], "non-postorder child"),
    ],
)
def test_malformed_native_hir_is_rejected(records, message):
    with pytest.raises(NativeHirContractError, match=message):
        lower_native_primitive_hir_records(records, "1")


def test_reference_rejects_untyped_unsupported_or_unresolved_shapes():
    with pytest.raises(PrimitiveHirLoweringError, match="outside executable"):
        lower_primitive_expression_hir(
            AstNode("identifier", 0, 1), "x", expected_type=I64
        )
    with pytest.raises(PrimitiveHirLoweringError, match="unresolved identifier"):
        lower_bound_expression_hir(
            AstNode("identifier", 0, 1), "x", expected_type=I64, bindings=()
        )
    with pytest.raises(PrimitiveHirLoweringError, match="duplicate resolved binding"):
        lower_bound_expression_hir(
            AstNode("identifier", 0, 1),
            "x",
            expected_type=I64,
            bindings=(("x", I64), ("x", I64)),
        )
    with pytest.raises(PrimitiveHirLoweringError, match="outside source"):
        lower_primitive_expression_hir(
            AstNode("exact_numeric", 3, 1), "1", expected_type=I64
        )
