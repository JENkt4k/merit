import pytest

from merit.bootstrap.ast_contract import (
    AstContractError, KIND_ADD, KIND_CALL, KIND_CONSTRUCTOR, KIND_DIVIDE,
    KIND_EQUAL, KIND_EXACT_NUMERIC, KIND_FIELD, KIND_FIELD_INITIALIZER,
    KIND_GENERIC_APPLY, KIND_GREATER, KIND_GREATER_EQUAL, KIND_GROUP,
    KIND_IDENTIFIER, KIND_INVALID, KIND_LESS, KIND_LESS_EQUAL, KIND_MULTIPLY,
    KIND_NOT_EQUAL, KIND_SEQUENCE, KIND_STRING, KIND_SUBTRACT,
    canonical_ast_json, lower_expression_ast,
)
from merit.bootstrap.ast_parity import ast_parity_observations, lower_native_ast_records


def test_bootstrap_ast_kind_representation_is_stable():
    assert (
        KIND_IDENTIFIER, KIND_EXACT_NUMERIC, KIND_STRING, KIND_GROUP, KIND_CALL,
        KIND_FIELD, KIND_GENERIC_APPLY, KIND_SEQUENCE, KIND_FIELD_INITIALIZER,
        KIND_INVALID, KIND_EQUAL, KIND_NOT_EQUAL, KIND_GREATER_EQUAL,
        KIND_LESS_EQUAL, KIND_GREATER, KIND_LESS, KIND_ADD, KIND_SUBTRACT,
        KIND_MULTIPLY, KIND_DIVIDE, KIND_CONSTRUCTOR,
    ) == (30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
          50, 51, 60, 61, 70)


def test_native_ast_records_reconstruct_canonical_tree():
    records = [
        (31, 0, 1, -1, -1, -1, 0, -1),
        (31, 2, 1, -1, -1, -1, 0, -1),
        (50, 0, 3, 0, 1, -1, 0, -1),
    ]
    native = lower_native_ast_records(records)
    reference = lower_expression_ast(
        [(31, 0, 1, -1, -1), (31, 2, 1, -1, -1), (50, 0, 3, 0, 1)]
    )
    assert native == reference
    assert canonical_ast_json(native) == canonical_ast_json(reference)


def test_native_group_records_preserve_nested_grouping_order():
    records = [
        (31, 2, 1, -1, -1, -1, 0, -1),
        (31, 2, 1, -1, -1, 1, 3, 0),
        (31, 2, 1, -1, -1, 0, 5, 1),
    ]
    node = lower_native_ast_records(records)
    assert node.kind == "exact_numeric"
    assert node.start == 2
    assert node.length == 1
    assert node.grouping_origins == ((1, 3), (0, 5))


def test_ast_parity_observations_use_real_canonical_artifacts():
    reference_records = [(31, 0, 1, -1, -1)]
    native_records = [(31, 0, 1, -1, -1, -1, 0, -1)]
    reference, bootstrap = ast_parity_observations(
        "literal", reference_records, native_records
    )
    assert reference.case_id == bootstrap.case_id == "literal"
    assert reference.stage == bootstrap.stage == "ast"
    assert reference.implementation == "reference"
    assert bootstrap.implementation == "bootstrap"
    assert reference.canonical == bootstrap.canonical
    assert reference.digest == bootstrap.digest


@pytest.mark.parametrize(
    "records,message",
    [
        ([], "empty"),
        ([(31, 0, 1, -1, -1, -1, 0)], "eight fields"),
        ([(999, 0, 1, -1, -1, -1, 0, -1)], "unknown native AST kind"),
        ([(31, -1, 1, -1, -1, -1, 0, -1)], "source span"),
        ([(31, 0, -1, -1, -1, -1, 0, -1)], "source span"),
        ([(31, 0, 1, 0, -1, -1, 0, -1)], "atom node"),
        ([(50, 0, 1, -1, -1, -1, 0, -1)], "child index"),
        ([(34, 0, 1, 0, -1, -1, 0, -1)], "child index"),
        ([(31, 0, 1, -1, -1, -2, 0, -1)], "grouping span"),
        ([(31, 0, 1, -1, -1, 0, 1, 0)], "grouping parent"),
    ],
)
def test_invalid_native_ast_records_are_rejected(records, message):
    with pytest.raises(AstContractError, match=message):
        lower_native_ast_records(records)


def test_native_ast_root_selection_is_checked():
    records = [(31, 0, 1, -1, -1, -1, 0, -1)]
    with pytest.raises(AstContractError, match="root index"):
        lower_native_ast_records(records, root_index=4)
