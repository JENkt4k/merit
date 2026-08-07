from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from merit.bootstrap.ast_contract import canonical_ast_json, lower_expression_ast
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")
CORPUS_PATH = Path(__file__).with_name("bootstrap_corpus_v1.json")


_KIND_NAMES = {
    30: "identifier",
    31: "exact_numeric",
    32: "string",
    34: "call",
    35: "field",
    36: "generic_apply",
    37: "sequence",
    38: "field_initializer",
    39: "invalid",
    40: "equal",
    41: "not_equal",
    42: "greater_equal",
    43: "less_equal",
    44: "greater",
    45: "less",
    50: "add",
    51: "subtract",
    60: "multiply",
    61: "divide",
    70: "constructor",
}
_ATOMS = {30, 31, 32, 39}
_REQUIRED_PAIR = {35, 40, 41, 42, 43, 44, 45, 50, 51, 60, 61}
_OPTIONAL_RIGHT = {34, 36, 37, 38, 70}


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


# Flat physical storage used by the Merit bootstrap. A group record copies its
# canonical child while linking grouping provenance to the previous physical
# record. This oracle is intentionally separate from the Merit implementation.
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


def canonical_data_from_flat(records, root_index: int | None = None):
    """Reconstruct canonical bootstrap-ast-v1 data from native flat records."""
    assert records
    selected = len(records) - 1 if root_index is None else root_index
    assert 0 <= selected < len(records)

    def grouping_origins(index: int):
        record = records[index]
        group_start, group_length, group_parent = record[5], record[6], record[7]
        origins = grouping_origins(group_parent) if group_parent >= 0 else []
        if group_start >= 0:
            origins = [*origins, [group_start, group_length]]
        return origins

    def build(index: int):
        kind, start, length, left, right, _, _, _ = records[index]
        assert kind in _KIND_NAMES
        children = []
        if kind in _ATOMS:
            assert left == -1 and right == -1
        elif kind in _REQUIRED_PAIR:
            assert 0 <= left < index
            assert 0 <= right < index
            children = [build(left), build(right)]
        elif kind in _OPTIONAL_RIGHT:
            assert 0 <= left < index
            children = [build(left)]
            if right != -1:
                assert 0 <= right < index
                children.append(build(right))
        else:
            raise AssertionError(f"unclassified flat AST kind {kind}")

        data = {
            "kind": _KIND_NAMES[kind],
            "start": start,
            "length": length,
            "children": children,
        }
        origins = grouping_origins(index)
        if origins:
            data["grouping_origins"] = origins
        return data

    return build(selected)


def canonical_json_from_flat(records) -> str:
    return json.dumps(
        canonical_data_from_flat(records), sort_keys=True, separators=(",", ":")
    )


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
    parser_records = REFERENCE.reference_expression(expression)
    expected_flat = reference_ast_records(expression)
    expected_canonical = lower_expression_ast(parser_records)
    expected_data = expected_canonical.to_data()
    expected_json = canonical_ast_json(expected_canonical)
    project, project_root = project_with_native_ast_probe(tmp_path, expression)

    interpreted_validation, interpreted_records = parse_ast_probe_output(interpret(project))
    assert interpreted_validation == 0
    assert interpreted_records == expected_flat
    assert canonical_data_from_flat(interpreted_records) == expected_data
    assert canonical_json_from_flat(interpreted_records) == expected_json

    _, _, executable = build(project, project_root / "bootstrap_native_ast")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native_validation, native_records = parse_ast_probe_output(native)
    assert native_validation == 0
    assert native_records == expected_flat
    assert native_records == interpreted_records
    assert canonical_data_from_flat(native_records) == expected_data
    assert canonical_json_from_flat(native_records) == expected_json


def test_merit_native_ast_group_records_preserve_nested_provenance(tmp_path):
    expression = "((1+2))*3"
    parser_records = REFERENCE.reference_expression(expression)
    expected = reference_ast_records(expression)
    expected_canonical = lower_expression_ast(parser_records)
    project, project_root = project_with_native_ast_probe(tmp_path, expression)

    validation, records = parse_ast_probe_output(interpret(project))
    assert validation == 0
    assert records == expected
    assert canonical_data_from_flat(records) == expected_canonical.to_data()
    assert canonical_json_from_flat(records) == canonical_ast_json(expected_canonical)

    grouped = [record for record in records if record[5] >= 0]
    assert len(grouped) == 2
    assert grouped[0][5:7] == (1, 5)
    assert grouped[1][5:7] == (0, 7)
    assert grouped[1][7] < len(records)

    _, _, executable = build(project, project_root / "bootstrap_nested_group_ast")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native_validation, native_records = parse_ast_probe_output(native)
    assert (native_validation, native_records) == (0, expected)
    assert canonical_data_from_flat(native_records) == expected_canonical.to_data()


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
