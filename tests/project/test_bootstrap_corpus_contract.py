from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from merit.bootstrap import AstContractError, canonical_ast_json, lower_expression_ast
from merit.project.build import build, interpret


ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = Path(__file__).with_name("bootstrap_corpus_v1.json")
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_reference_oracle", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _case_ids(section: str) -> list[str]:
    return [case["id"] for case in CORPUS[section]]


def test_bootstrap_corpus_v1_is_well_formed_and_uniquely_named():
    assert CORPUS["contract"] == "bootstrap-corpus-v1"
    all_ids = _case_ids("source_cases") + _case_ids("expression_cases")
    assert len(all_ids) == len(set(all_ids))
    assert len(CORPUS["source_cases"]) >= 11
    assert len(CORPUS["expression_cases"]) >= 12

    allowed_comparisons = {
        "tokens",
        "syntax",
        "diagnostics",
        "ast",
        "interpreter",
        "native",
    }
    for case in CORPUS["source_cases"]:
        assert case["source"]
        assert set(case["compare"]) <= allowed_comparisons
        assert {"tokens", "syntax", "diagnostics", "interpreter", "native"} <= set(
            case["compare"]
        )


@pytest.mark.parametrize(
    "case", CORPUS["source_cases"], ids=_case_ids("source_cases")
)
def test_manifest_source_case_matches_reference_interpreter_and_native(tmp_path, case):
    project, project_root = REFERENCE.project_with_source(tmp_path, case["source"])
    expected = REFERENCE.expected_output(case["source"])
    assert interpret(project) == expected

    _, _, executable = build(project, project_root / "bootstrap_corpus_source")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


@pytest.mark.parametrize(
    "case", CORPUS["expression_cases"], ids=_case_ids("expression_cases")
)
def test_manifest_expression_case_matches_ast_interpreter_and_native(tmp_path, case):
    records = REFERENCE.reference_expression(case["expression"])
    ast = lower_expression_ast(records)
    assert ast.kind == case["root_kind"]
    assert json.loads(canonical_ast_json(ast)) == ast.to_data()

    project, project_root = REFERENCE.project_with_expression(
        tmp_path, case["expression"]
    )
    expected = REFERENCE.expected_output(
        REFERENCE.DEFAULT_SOURCE, case["expression"]
    )
    assert interpret(project) == expected

    _, _, executable = build(project, project_root / "bootstrap_corpus_expression")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


def test_bootstrap_ast_removes_group_node_but_retains_grouping_provenance():
    records = REFERENCE.reference_expression("(1+2)*3")
    ast = lower_expression_ast(records)

    assert ast.kind == "multiply"
    grouped_add = ast.children[0]
    assert grouped_add.kind == "add"
    assert grouped_add.grouping_origins == ((0, 5),)
    assert all(child.kind != "group" for child in ast.children)


def test_bootstrap_ast_rejects_unknown_or_forward_references():
    with pytest.raises(AstContractError, match="unknown bootstrap expression kind"):
        lower_expression_ast([(999, 0, 1, -1, -1)])

    with pytest.raises(AstContractError, match="is not before node"):
        lower_expression_ast([(50, 0, 1, 1, 1)])


def test_bootstrap_ast_serialization_is_deterministic():
    records = REFERENCE.reference_expression("f(1,2+3).value")
    ast = lower_expression_ast(records)
    first = canonical_ast_json(ast)
    second = canonical_ast_json(lower_expression_ast(tuple(records)))
    assert first == second
    assert " " not in first
