from __future__ import annotations

import pytest

from merit.bootstrap.ast_contract import AstNode
from merit.bootstrap.hir_contract import HirType, canonical_hir_json
from merit.bootstrap.hir_expression import PrimitiveHirLoweringError, lower_resolved_expression_hir
from merit.bootstrap.hir_string_parity import (
    NativeStringHirError,
    lower_native_complete_expression_hir_records,
)


STRING = HirType("string")


def test_reference_string_literal_preserves_spelling_without_numeric_policy():
    hir = lower_resolved_expression_hir(
        AstNode("string", 0, 7),
        '"value"',
        expected_type=STRING,
        module_name="string-atom",
    )
    assert hir.roots == (0,)
    assert len(hir.nodes) == 1
    node = hir.nodes[0]
    assert node.kind == "literal"
    assert node.type == STRING
    assert node.value == '"value"'
    assert node.numeric_policy is None


def test_reference_string_literal_requires_explicit_semantic_type():
    with pytest.raises(PrimitiveHirLoweringError, match="explicit type"):
        lower_resolved_expression_hir(
            AstNode("string", 0, 7),
            '"value"',
            expected_type=None,
            module_name="string-atom",
        )


def test_native_string_record_matches_reference_canonical_hir():
    source = '"value"'
    native = lower_native_complete_expression_hir_records(
        [(12, 0, 7, -1, -1, 0, 6, 0, -1)],
        source,
        module_name="string-atom",
        type_names={6: STRING},
    )
    reference = lower_resolved_expression_hir(
        AstNode("string", 0, 7),
        source,
        expected_type=STRING,
        module_name="string-atom",
    )
    assert canonical_hir_json(native) == canonical_hir_json(reference)


def test_native_string_rejects_numeric_policy():
    with pytest.raises(NativeStringHirError, match="numeric policy"):
        lower_native_complete_expression_hir_records(
            [(12, 0, 7, -1, -1, 0, 6, 1, -1)],
            '"value"',
            type_names={6: STRING},
        )


def test_native_string_rejects_unresolved_type_code():
    with pytest.raises(NativeStringHirError, match="type code"):
        lower_native_complete_expression_hir_records(
            [(12, 0, 7, -1, -1, 0, 6, 0, -1)],
            '"value"',
        )


def test_native_string_requires_quoted_source_span():
    with pytest.raises(NativeStringHirError, match="quoted source spelling"):
        lower_native_complete_expression_hir_records(
            [(12, 0, 5, -1, -1, 0, 6, 0, -1)],
            "value",
            type_names={6: STRING},
        )
