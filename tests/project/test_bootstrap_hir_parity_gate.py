from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.ast_contract import lower_expression_ast
from merit.bootstrap.hir_contract import HirType
from merit.bootstrap.hir_expression import lower_bound_expression_hir
from merit.bootstrap.hir_parity import primitive_hir_parity_observations
from merit.bootstrap.parity import build_parity_report, markdown_summary
from merit.bootstrap.repository_corpus import load_repository_corpus
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
MANIFEST = ROOT / "tests/project/bootstrap_corpus_v1.json"
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")
I64 = HirType("i64")


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_hir_parity_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()


def _probe_source(expressions: list[str]) -> str:
    calls = []
    for index, expression in enumerate(expressions):
        literal = json.dumps(expression)
        calls.append(
            f"        let source_{index}: Buffer = buffer_from_string(allocator, {literal});\n"
            f"        emit_hir_case(source_{index}, allocator);\n"
            f"        drop(source_{index});"
        )
    body = "\n".join(calls)
    return f'''module bootstrap_hir_parity_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_hir;

capability allocate;

fn emit_hir_case(borrow source: Buffer, allocator: Allocator) -> i32
requires_caps [allocate]
{{
    let tokens: Vec<Token> = lex(source, allocator);
    let expressions: Vec<ExpressionNode> = parse_expression_tokens(source, tokens, allocator);
    let ast_nodes: Vec<AstNodeRecord> = lower_expression_ast_records(expressions, allocator);
    var hir_nodes: Vec<HirExpressionRecord> = vec_new<HirExpressionRecord>(allocator, vec_len<AstNodeRecord>(ast_nodes));
    var binding_starts: Vec<i64> = vec_new<i64>(allocator, 4);
    var binding_lengths: Vec<i64> = vec_new<i64>(allocator, 4);
    var ast_index: i64 = 0;
    while (ast_index < vec_len<AstNodeRecord>(ast_nodes)) {{
        let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_index);
        var binding_id: i64 = -1;
        if ast_kind(ast) == 30 {{
            if ast_group_parent(ast) < 0 {{
                binding_id = hir_find_binding_id(
                    source,
                    binding_starts,
                    binding_lengths,
                    ast_start(ast),
                    ast_length(ast)
                );
                if binding_id < 0 {{
                    binding_id = vec_len<i64>(binding_starts);
                    vec_push<i64>(binding_starts, ast_start(ast));
                    vec_push<i64>(binding_lengths, ast_length(ast));
                }}
            }}
        }}
        let hir: HirExpressionRecord = lower_primitive_hir_record(
            ast_kind(ast),
            ast_start(ast),
            ast_length(ast),
            ast_left(ast),
            ast_right(ast),
            ast_group_start(ast),
            ast_group_length(ast),
            ast_group_parent(ast),
            binding_id
        );
        vec_push<HirExpressionRecord>(hir_nodes, hir);
        ast_index = checked_add(ast_index, 1);
    }}
    print(validate_primitive_hir_records(hir_nodes));
    print(vec_len<HirExpressionRecord>(hir_nodes));
    var index: i64 = 0;
    while (index < vec_len<HirExpressionRecord>(hir_nodes)) {{
        let node: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, index);
        print(hir_kind(node));
        print(hir_start(node));
        print(hir_length(node));
        print(hir_left(node));
        print(hir_right(node));
        print(hir_symbol(node));
        print(hir_type_code(node));
        print(hir_numeric_policy(node));
        print(hir_binding_id(node));
        index = checked_add(index, 1);
    }}
    drop(binding_lengths);
    drop(binding_starts);
    drop(hir_nodes);
    drop(ast_nodes);
    drop(expressions);
    drop(tokens);
    return 0;
}}

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
{body}
    }}
    return 0;
}}
'''


def _project_with_probe(tmp_path: Path, expressions: list[str]):
    project_root = tmp_path / "bootstrap_hir_parity"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))

    lexer_path = project_root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")

    (project_root / "src/hir_parity_probe.mrt").write_text(
        _probe_source(expressions), encoding="utf-8"
    )
    manifest = project_root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/hir_parity_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), project_root


def _parse_probe_output(output: str, case_count: int):
    values = [int(value) for value in output.splitlines()]
    cursor = 0
    cases = []
    for _ in range(case_count):
        assert cursor + 2 <= len(values)
        validation = values[cursor]
        count = values[cursor + 1]
        cursor += 2
        field_count = count * 9
        assert cursor + field_count <= len(values)
        fields = values[cursor : cursor + field_count]
        cursor += field_count
        records = [
            tuple(fields[index : index + 9])
            for index in range(0, len(fields), 9)
        ]
        cases.append((validation, records))
    assert cursor == len(values)
    return cases


def _reference_hir(case):
    records = REFERENCE.reference_expression(case.text)
    ast = lower_expression_ast(records)
    binding_names: list[str] = []
    for kind, start, length, _, _ in records:
        if kind != 30:
            continue
        name = case.text[start : start + length]
        if name not in binding_names:
            binding_names.append(name)
    return lower_bound_expression_hir(
        ast,
        case.text,
        expected_type=I64,
        bindings=((name, I64) for name in binding_names),
        module_name=case.case_id,
    )


def _observations(cases, actual):
    observations = []
    for case, (validation, records) in zip(cases, actual, strict=True):
        assert validation == 0, case.case_id
        observations.extend(
            primitive_hir_parity_observations(
                case.case_id, _reference_hir(case), records, case.text
            )
        )
    return observations


def test_repository_bound_expression_hir_has_real_interpreter_and_native_parity(tmp_path):
    corpus = load_repository_corpus(MANIFEST)
    cases = corpus.for_stage("hir")
    assert [case.case_id for case in cases] == [
        "precedence-product",
        "explicit-group",
        "left-associative-subtract",
        "comparison-last",
        "division-before-addition",
    ]
    expressions = [case.text for case in cases]
    project, project_root = _project_with_probe(tmp_path, expressions)

    interpreted = _parse_probe_output(interpret(project), len(cases))
    interpreted_report = build_parity_report(
        corpus, _observations(cases, interpreted), stages=["hir"]
    )
    assert interpreted_report.complete, markdown_summary(interpreted_report)
    assert interpreted_report.stage_counts() == {"hir": (5, 5)}

    _, _, executable = build(project, project_root / "hir_parity")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native = _parse_probe_output(native_output, len(cases))
    native_report = build_parity_report(
        corpus, _observations(cases, native), stages=["hir"]
    )
    assert native_report.complete, markdown_summary(native_report)
    assert native_report.stage_counts() == {"hir": (5, 5)}

    assert native == interpreted
