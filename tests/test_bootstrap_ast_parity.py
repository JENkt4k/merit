import pytest

from merit.bootstrap.ast_contract import AstContractError, canonical_ast_json, lower_expression_ast
from merit.bootstrap.ast_parity import ast_parity_observations, lower_native_ast_records


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
