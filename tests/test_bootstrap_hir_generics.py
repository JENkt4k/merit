from __future__ import annotations

import json

import pytest

from merit.bootstrap.ast_contract import AstNode
from merit.bootstrap.hir_contract import HirType, canonical_hir_json, load_hir_json
from merit.bootstrap.hir_expression import (
    HirFunctionSignature,
    PrimitiveHirLoweringError,
    lower_resolved_expression_hir,
)
from merit.bootstrap.hir_generic_parity import (
    NativeGenericHirError,
    lower_native_generic_hir_records,
)


I64 = HirType("i64")
TYPE_T = HirType("T")


def _generic_call_ast() -> AstNode:
    callee = AstNode("identifier", 0, 8)
    type_argument = AstNode("identifier", 9, 3)
    generic = AstNode("generic_apply", 0, 13, (callee, type_argument))
    argument = AstNode("exact_numeric", 14, 1)
    return AstNode("call", 0, 16, (generic, argument))


def _identity_signature() -> HirFunctionSignature:
    return HirFunctionSignature("identity", (TYPE_T,), TYPE_T, ("T",))


def test_reference_generic_call_substitutes_parameter_and_result_types():
    hir = lower_resolved_expression_hir(
        _generic_call_ast(),
        "identity<i64>(1)",
        expected_type=I64,
        functions=(_identity_signature(),),
        types=(I64,),
        module_name="single-generic-call",
    )
    assert [node.kind for node in hir.nodes] == ["literal", "call"]
    assert hir.nodes[0].type == I64
    assert hir.nodes[1].type == I64
    assert hir.nodes[1].symbol == "identity"
    assert hir.nodes[1].children == (0,)
    assert hir.nodes[1].generic_arguments == (I64,)


def test_native_generic_symbol_span_reconstructs_same_canonical_hir():
    source = "identity<i64>(1)"
    reference = lower_resolved_expression_hir(
        _generic_call_ast(),
        source,
        expected_type=I64,
        functions=(_identity_signature(),),
        types=(I64,),
        module_name="single-generic-call",
    )
    native = lower_native_generic_hir_records(
        [
            (9, 0, 8, -1, -1, 0, 0, 0, -2),
            (9, 9, 3, -1, -1, 0, 0, 0, -2),
            (9, 0, 13, -1, -1, 0, 0, 0, -2),
            (1, 14, 1, -1, -1, 0, 1, 1, -1),
            (6, 0, 16, 2, 3, 0, 1, 0, -1),
        ],
        source,
        module_name="single-generic-call",
        generic_types={"i64": I64},
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


def test_generic_arguments_round_trip_through_hir_json():
    module = lower_resolved_expression_hir(
        _generic_call_ast(),
        "identity<i64>(1)",
        expected_type=I64,
        functions=(_identity_signature(),),
        types=(I64,),
    )
    encoded = canonical_hir_json(module)
    assert json.loads(encoded)["nodes"][-1]["generic_arguments"] == [{"name": "i64"}]
    assert load_hir_json(encoded) == module


def test_reference_generic_call_rejects_missing_type_environment():
    with pytest.raises(PrimitiveHirLoweringError, match="unresolved type argument"):
        lower_resolved_expression_hir(
            _generic_call_ast(),
            "identity<i64>(1)",
            expected_type=I64,
            functions=(_identity_signature(),),
        )


def test_native_generic_call_rejects_unresolved_type_argument():
    with pytest.raises(NativeGenericHirError, match="unresolved generic type argument"):
        lower_native_generic_hir_records(
            [
                (9, 0, 13, -1, -1, 0, 0, 0, -2),
                (1, 14, 1, -1, -1, 0, 1, 1, -1),
                (6, 0, 16, 0, 1, 0, 1, 0, -1),
            ],
            "identity<i64>(1)",
        )
