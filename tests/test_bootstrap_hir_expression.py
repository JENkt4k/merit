from __future__ import annotations

import pytest

from merit.bootstrap.ast_contract import AstNode
from merit.bootstrap.hir_contract import HirType, canonical_hir_json
from merit.bootstrap.hir_expression import (
    HirFieldSignature,
    HirFunctionSignature,
    PrimitiveHirLoweringError,
    lower_bound_expression_hir,
    lower_primitive_expression_hir,
    lower_resolved_expression_hir,
)
from merit.bootstrap.hir_parity import (
    NativeHirContractError,
    lower_native_primitive_hir_records,
)


I64 = HirType("i64")
BOOL = HirType("bool")
ACCOUNT = HirType("Account")
RECORD = HirType("Record")


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


def test_resolved_empty_call_uses_symbol_without_creating_binding_node():
    callee = AstNode("identifier", 0, 1)
    root = AstNode("call", 0, 3, (callee,))
    reference = lower_resolved_expression_hir(
        root,
        "f()",
        expected_type=I64,
        functions=(HirFunctionSignature("f", (), I64),),
        module_name="empty-call",
    )
    assert reference.bindings == ()
    assert len(reference.nodes) == 1
    assert reference.nodes[0].kind == "call"
    assert reference.nodes[0].symbol == "f"
    assert reference.nodes[0].children == ()

    native = lower_native_primitive_hir_records(
        [
            (9, 0, 1, -1, -1, 0, 0, 0, -2),
            (6, 0, 3, 0, -1, 0, 1, 0, -1),
        ],
        "f()",
        module_name="empty-call",
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


def test_resolved_call_flattens_argument_sequence_in_source_order():
    source = "f(1,2+3)"
    callee = AstNode("identifier", 0, 1)
    one = AstNode("exact_numeric", 2, 1)
    two = AstNode("exact_numeric", 4, 1)
    three = AstNode("exact_numeric", 6, 1)
    add = AstNode("add", 4, 3, (two, three))
    arguments = AstNode("sequence", 2, 5, (one, add))
    root = AstNode("call", 0, 8, (callee, arguments))
    reference = lower_resolved_expression_hir(
        root,
        source,
        expected_type=I64,
        functions=(HirFunctionSignature("f", (I64, I64), I64),),
        module_name="argument-sequence",
    )
    assert [node.kind for node in reference.nodes] == [
        "literal", "literal", "literal", "binary", "call"
    ]
    assert reference.nodes[-1].children == (0, 3)
    assert reference.nodes[-1].symbol == "f"

    native = lower_native_primitive_hir_records(
        [
            (9, 0, 1, -1, -1, 0, 0, 0, -2),
            (1, 2, 1, -1, -1, 0, 1, 1, -1),
            (1, 4, 1, -1, -1, 0, 1, 1, -1),
            (1, 6, 1, -1, -1, 0, 1, 1, -1),
            (2, 4, 3, 2, 3, 1, 1, 2, -1),
            (8, 2, 5, 1, 4, 0, 0, 0, -1),
            (6, 0, 8, 0, 5, 0, 1, 0, -1),
        ],
        source,
        module_name="argument-sequence",
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


def test_resolved_field_uses_receiver_type_and_omits_field_symbol_node():
    source = "account.balance+1"
    account = AstNode("identifier", 0, 7)
    balance = AstNode("identifier", 8, 7)
    field = AstNode("field", 0, 15, (account, balance))
    one = AstNode("exact_numeric", 16, 1)
    root = AstNode("add", 0, 17, (field, one))
    reference = lower_resolved_expression_hir(
        root,
        source,
        expected_type=I64,
        bindings=(("account", ACCOUNT),),
        fields=(HirFieldSignature(ACCOUNT, "balance", I64),),
        module_name="field-before-addition",
    )
    assert [node.kind for node in reference.nodes] == ["identifier", "field", "literal", "binary"]
    assert reference.nodes[0].type == ACCOUNT
    assert reference.nodes[1].children == (0,)
    assert reference.nodes[1].symbol == "balance"

    native = lower_native_primitive_hir_records(
        [
            (4, 0, 7, -1, -1, 0, 3, 0, 0),
            (9, 8, 7, -1, -1, 0, 0, 0, -2),
            (7, 0, 15, 0, 1, 0, 1, 0, -1),
            (1, 16, 1, -1, -1, 0, 1, 1, -1),
            (2, 0, 17, 2, 3, 1, 1, 2, -1),
        ],
        source,
        module_name="field-before-addition",
        type_names={3: ACCOUNT},
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
        ([(6, 0, 3, 0, -1, 0, 1, 0, -1)], "non-symbol"),
        ([(9, 0, 1, -1, -1, 0, 1, 0, -2)], "symbol reference"),
        ([(8, 0, 1, -1, -1, 0, 0, 0, -1)], "argument child"),
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
    with pytest.raises(PrimitiveHirLoweringError, match="unresolved function"):
        lower_resolved_expression_hir(
            AstNode("call", 0, 3, (AstNode("identifier", 0, 1),)),
            "f()",
            expected_type=I64,
        )
    with pytest.raises(PrimitiveHirLoweringError, match="unresolved field"):
        lower_resolved_expression_hir(
            AstNode(
                "field",
                0,
                3,
                (AstNode("identifier", 0, 1), AstNode("identifier", 2, 1)),
            ),
            "a.b",
            expected_type=I64,
            bindings=(("a", ACCOUNT),),
        )
