from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")
CORPUS_PATH = Path(__file__).with_name("bootstrap_corpus_v1.json")


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_ast_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


# Flat canonical storage used by the Merit bootstrap. The recursive
# bootstrap-ast-v1 tree is reconstructed by following left/right child indices.
# A group record is a copy of its canonical child with one grouping origin and
# a link to the previous record, preserving arbitrarily nested grouping without
# recursive owned storage in the stage-0 implementation.
def reference_ast_records(expression: str):
    expressions = REFERENCE.reference_expression(expression)
    lowered = []
    for index, (kind, start, length, left, right) in enumerate(expressions):
        if kind == 33:
            assert 0 <= left < index
            child = lowered[left]
            lowered.append(
                (
                    child[0],
                    child[1],
                    child[2],
                    child[3],
                    child[4],
                    start,
                    length,
                    left,
                )
            )
        else:
            lowered.append((kind, start, length, left, right, -1, 0, -1))
    return lowered


def _inject_ast_probe(source: str) -> str:
    probe = '''        print(-4);
        print(validate_expression_ast_records(expressions));
        let ast_nodes: Vec<AstNodeRecord> = lower_expression_ast_records(expressions, allocator);
        print(vec_len<AstNodeRecord>(ast_nodes));
        var ast_index: i64 = 0;
        while (ast_index < vec_len<AstNodeRecord>(ast_nodes)) {
            let ast_node: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_index);
            print(ast_kind(ast_node));
            print(ast_start(ast_node));
            print(ast_length(ast_node));
            print(ast_left(ast_node));
            print(ast_right(ast_node));
            print(ast_group_start(ast_node));
            print(ast_group_length(ast_node));
            print(ast_group_parent(ast_node));
            ast_index = checked_add(ast_index, 1);
        }
'''
    marker = "        drop(expressions);\n"
    assert marker in source
    return source.replace(marker, probe + marker, 1)


def project_with_native_ast_probe(tmp_path, expression: str):
    project_root = tmp_path / "bootstrap_native_ast"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    source = lexer_path.read_text(encoding="utf-8")
    replacement = (
        "        let expression_source: Buffer = buffer_from_string(allocator, "
        f"{json.dumps(expression)});"
    )
    source, replacements = re.subn(
        r"^        let expression_source: Buffer = buffer_from_string\(allocator, .+\);$",
        lambda _: replacement,
        source,
        count=1,
        flags=re.MULTILINE,
    )
    assert replacements == 1
    lexer_path.write_text(_inject_ast_probe(source), encoding="utf-8")
    return load_project(project_root / "Merit.toml"), project_root


def parse_ast_probe_output(output: str):
    marker = "-4\n"
    assert marker in output
    payload = output.rsplit(marker, 1)[1]
    values = [int(value) for value in payload.splitlines()]
    assert len(values) >= 2
    validation = values[0]
    count = values[1]
    fields = values[2:]
    assert len(fields) == count * 8
    records = [tuple(fields[index : index + 8]) for index in range(0, len(fields), 8)]
    return validation, records


@pytest.mark.parametrize(
    "case",
    CORPUS["expression_cases"],
    ids=[case["id"] for case in CORPUS["expression_cases"]],
)
def test_merit_native_ast_matches_independent_flat_contract_interpreter_and_native(
    tmp_path, case
):
    expression = case["expression"]
    expected = reference_ast_records(expression)
    project, project_root = project_with_native_ast_probe(tmp_path, expression)

    interpreted_validation, interpreted_records = parse_ast_probe_output(interpret(project))
    assert interpreted_validation == 0
    assert interpreted_records == expected

    _, _, executable = build(project, project_root / "bootstrap_native_ast")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native_validation, native_records = parse_ast_probe_output(native)
    assert native_validation == 0
    assert native_records == expected
    assert native_records == interpreted_records


def test_merit_native_ast_group_records_preserve_nested_provenance(tmp_path):
    expression = "((1+2))*3"
    expected = reference_ast_records(expression)
    project, project_root = project_with_native_ast_probe(tmp_path, expression)

    validation, records = parse_ast_probe_output(interpret(project))
    assert validation == 0
    assert records == expected

    grouped = [record for record in records if record[5] >= 0]
    assert len(grouped) == 2
    assert grouped[0][5:7] == (1, 5)
    assert grouped[1][5:7] == (0, 7)
    assert grouped[1][7] < len(records)

    _, _, executable = build(project, project_root / "bootstrap_nested_group_ast")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert parse_ast_probe_output(native) == (0, expected)


def _inject_validation_probe(source: str) -> str:
    probe = '''        print(-5);
        var empty_records: Vec<ExpressionNode> = vec_new<ExpressionNode>(allocator, 0);
        print(validate_expression_ast_records(empty_records));
        drop(empty_records);
        var negative_span: Vec<ExpressionNode> = vec_new<ExpressionNode>(allocator, 1);
        vec_push<ExpressionNode>(negative_span, ExpressionNode { kind: 30, start: -1, length: 1, left: -1, right: -1 });
        print(validate_expression_ast_records(negative_span));
        drop(negative_span);
        var unknown_kind: Vec<ExpressionNode> = vec_new<ExpressionNode>(allocator, 1);
        vec_push<ExpressionNode>(unknown_kind, ExpressionNode { kind: 999, start: 0, length: 1, left: -1, right: -1 });
        print(validate_expression_ast_records(unknown_kind));
        drop(unknown_kind);
        var atom_children: Vec<ExpressionNode> = vec_new<ExpressionNode>(allocator, 1);
        vec_push<ExpressionNode>(atom_children, ExpressionNode { kind: 30, start: 0, length: 1, left: 0, right: -1 });
        print(validate_expression_ast_records(atom_children));
        drop(atom_children);
        var forward_child: Vec<ExpressionNode> = vec_new<ExpressionNode>(allocator, 1);
        vec_push<ExpressionNode>(forward_child, ExpressionNode { kind: 50, start: 0, length: 3, left: 1, right: 1 });
        print(validate_expression_ast_records(forward_child));
        drop(forward_child);
'''
    marker = "        drop(expressions);\n"
    assert marker in source
    return source.replace(marker, probe + marker, 1)


def test_merit_native_ast_validation_rejects_malformed_contract_records(tmp_path):
    project_root = tmp_path / "bootstrap_ast_validation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    source = lexer_path.read_text(encoding="utf-8")
    lexer_path.write_text(_inject_validation_probe(source), encoding="utf-8")
    project = load_project(project_root / "Merit.toml")

    interpreted = interpret(project)
    payload = interpreted.rsplit("-5\n", 1)[1]
    assert [int(value) for value in payload.splitlines()] == [8, 1, 2, 4, 5]

    _, _, executable = build(project, project_root / "bootstrap_ast_validation")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native_payload = native.rsplit("-5\n", 1)[1]
    assert [int(value) for value in native_payload.splitlines()] == [8, 1, 2, 4, 5]
