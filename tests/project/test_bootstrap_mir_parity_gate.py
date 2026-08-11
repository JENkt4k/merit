from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.ast_contract import lower_expression_ast
from merit.bootstrap.hir_contract import HirType
from merit.bootstrap.hir_expression import lower_resolved_expression_hir
from merit.bootstrap.mir_parity import expression_mir_parity_observations
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
        "merit_bootstrap_mir_parity_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()


def _bindings(case_id: str) -> tuple[tuple[str, HirType], ...]:
    if case_id == "left-associative-subtract":
        return (("a", I64), ("b", I64), ("c", I64))
    if case_id == "comparison-last":
        return (("a", I64), ("b", I64))
    if case_id == "division-before-addition":
        return (("a", I64),)
    return ()


def _reference_hir(case):
    ast = lower_expression_ast(REFERENCE.reference_expression(case.text))
    return lower_resolved_expression_hir(
        ast,
        case.text,
        expected_type=I64,
        bindings=_bindings(case.case_id),
        module_name=case.case_id,
    )


def _probe_source(cases) -> str:
    declarations: list[str] = []
    executions: list[str] = []
    for index, case in enumerate(cases):
        literal = json.dumps(case.text)
        declarations.append(
            f"        let source_{index}: Buffer = buffer_from_string(allocator, {literal});"
        )
        executions.append(
            f"        emit_mir_case(source_{index}, allocator);\n"
            f"        drop(source_{index});"
        )
    body = "\n".join(declarations + executions)
    return f'''module bootstrap_mir_parity_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_hir;
import bootstrap_mir;

capability allocate;

fn resolved_hir_type_code(borrow ast_nodes: Vec<AstNodeRecord>, index: i64) -> i32 {{
    let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, index);
    if (ast_group_parent(ast) >= 0) {{ return 1; }}
    if (ast_kind(ast) == 40) {{ return 2; }}
    if (ast_kind(ast) == 41) {{ return 2; }}
    if (ast_kind(ast) == 42) {{ return 2; }}
    if (ast_kind(ast) == 43) {{ return 2; }}
    if (ast_kind(ast) == 44) {{ return 2; }}
    if (ast_kind(ast) == 45) {{ return 2; }}
    return 1;
}}

fn emit_mir_case(borrow source: Buffer, allocator: Allocator) -> i32
requires_caps [allocate]
{{
    let tokens: Vec<Token> = lex(source, allocator);
    let expressions: Vec<ExpressionNode> = parse_expression_tokens(source, tokens, allocator);
    let ast_nodes: Vec<AstNodeRecord> = lower_expression_ast_records(expressions, allocator);

    var hir_nodes: Vec<HirExpressionRecord> = vec_new<HirExpressionRecord>(
        allocator,
        vec_len<AstNodeRecord>(ast_nodes)
    );
    var binding_starts: Vec<i64> = vec_new<i64>(allocator, 4);
    var binding_lengths: Vec<i64> = vec_new<i64>(allocator, 4);
    var ast_index: i64 = 0;
    while (ast_index < vec_len<AstNodeRecord>(ast_nodes)) {{
        let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_index);
        var binding_id: i64 = -1;
        if (ast_kind(ast) == 30) {{
            if (ast_group_parent(ast) < 0) {{
                binding_id = hir_find_binding_id(
                    source,
                    binding_starts,
                    binding_lengths,
                    ast_start(ast),
                    ast_length(ast)
                );
                if (binding_id < 0) {{
                    binding_id = vec_len<i64>(binding_starts);
                    vec_push<i64>(binding_starts, ast_start(ast));
                    vec_push<i64>(binding_lengths, ast_length(ast));
                }}
            }}
        }}
        let hir: HirExpressionRecord = lower_resolved_hir_record(
            ast_kind(ast),
            ast_start(ast),
            ast_length(ast),
            ast_left(ast),
            ast_right(ast),
            ast_group_start(ast),
            ast_group_length(ast),
            ast_group_parent(ast),
            binding_id,
            resolved_hir_type_code(ast_nodes, ast_index)
        );
        vec_push<HirExpressionRecord>(hir_nodes, hir);
        ast_index = checked_add(ast_index, 1);
    }}

    if (validate_primitive_hir_records(hir_nodes) != 0) {{
        print(90);
        print(0);
        drop(binding_lengths);
        drop(binding_starts);
        drop(hir_nodes);
        drop(ast_nodes);
        drop(expressions);
        drop(tokens);
        return 90;
    }}

    let binding_count: i64 = vec_len<i64>(binding_starts);
    let hir_count: i64 = vec_len<HirExpressionRecord>(hir_nodes);
    var local_ids: Vec<i64> = vec_new<i64>(allocator, hir_count);
    var canonical_ids: Vec<i64> = vec_new<i64>(allocator, hir_count);
    var initialize_index: i64 = 0;
    while (initialize_index < hir_count) {{
        vec_push<i64>(local_ids, -1);
        vec_push<i64>(canonical_ids, -1);
        initialize_index = checked_add(initialize_index, 1);
    }}

    // HIR records are postorder, while MIR temporary locals are allocated when
    // entering a value node. Walk root-first with an explicit stack so the native
    // replacement owns deterministic local numbering rather than the adapter.
    var stack: Vec<i64> = vec_new<i64>(allocator, hir_count);
    vec_push<i64>(stack, checked_sub(hir_count, 1));
    var next_temporary: i64 = binding_count;
    while (vec_len<i64>(stack) > 0) {{
        let current_index: i64 = vec_pop<i64>(stack);
        let current: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, current_index);
        if (hir_kind(current) == 3) {{
            vec_push<i64>(stack, hir_left(current));
        }} else {{
            if (hir_kind(current) == 4) {{
                vec_set<i64>(local_ids, current_index, hir_binding_id(current));
            }} else {{
                if (vec_get<i64>(local_ids, current_index) < 0) {{
                    vec_set<i64>(local_ids, current_index, next_temporary);
                    next_temporary = checked_add(next_temporary, 1);
                }}
                if (hir_kind(current) == 2) {{
                    vec_push<i64>(stack, hir_right(current));
                    vec_push<i64>(stack, hir_left(current));
                }}
                if (hir_kind(current) == 5) {{
                    vec_push<i64>(stack, hir_right(current));
                    vec_push<i64>(stack, hir_left(current));
                }}
            }}
        }}
    }}

    // Canonical HIR IDs remain postorder and structural grouping aliases do not
    // consume IDs. Resolve aliases only after the semantic child has an ID/local.
    var next_hir_id: i64 = 0;
    var canonical_index: i64 = 0;
    while (canonical_index < hir_count) {{
        let current: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, canonical_index);
        if (hir_kind(current) == 3) {{
            vec_set<i64>(
                local_ids,
                canonical_index,
                vec_get<i64>(local_ids, hir_left(current))
            );
            vec_set<i64>(
                canonical_ids,
                canonical_index,
                vec_get<i64>(canonical_ids, hir_left(current))
            );
        }} else {{
            vec_set<i64>(canonical_ids, canonical_index, next_hir_id);
            next_hir_id = checked_add(next_hir_id, 1);
        }}
        canonical_index = checked_add(canonical_index, 1);
    }}

    var mir_nodes: Vec<MirExpressionRecord> = vec_new<MirExpressionRecord>(allocator, hir_count);
    var hir_index: i64 = 0;
    while (hir_index < hir_count) {{
        let hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, hir_index);
        var left_local: i64 = -1;
        var right_local: i64 = -1;
        if (hir_kind(hir) == 2) {{
            left_local = vec_get<i64>(local_ids, hir_left(hir));
            right_local = vec_get<i64>(local_ids, hir_right(hir));
        }}
        if (hir_kind(hir) == 5) {{
            left_local = vec_get<i64>(local_ids, hir_left(hir));
            right_local = vec_get<i64>(local_ids, hir_right(hir));
        }}
        if (hir_kind(hir) == 3) {{
            left_local = vec_get<i64>(local_ids, hir_left(hir));
        }}
        let mir: MirExpressionRecord = lower_expression_mir_record(
            hir,
            left_local,
            right_local,
            vec_get<i64>(local_ids, hir_index),
            vec_get<i64>(canonical_ids, hir_index)
        );
        vec_push<MirExpressionRecord>(mir_nodes, mir);
        hir_index = checked_add(hir_index, 1);
    }}

    print(validate_expression_mir_records(mir_nodes));
    print(vec_len<MirExpressionRecord>(mir_nodes));
    var index: i64 = 0;
    while (index < vec_len<MirExpressionRecord>(mir_nodes)) {{
        let node: MirExpressionRecord = vec_get<MirExpressionRecord>(mir_nodes, index);
        print(mir_kind(node));
        print(mir_start(node));
        print(mir_length(node));
        print(mir_result(node));
        print(mir_left(node));
        print(mir_right(node));
        print(mir_symbol(node));
        print(mir_type_code(node));
        print(mir_numeric_policy(node));
        print(mir_binding_id(node));
        print(mir_hir_node_id(node));
        index = checked_add(index, 1);
    }}

    drop(mir_nodes);
    drop(stack);
    drop(canonical_ids);
    drop(local_ids);
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


def _project_with_probe(tmp_path: Path, cases):
    project_root = tmp_path / "bootstrap_mir_parity"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (project_root / "src/mir_parity_probe.mrt").write_text(
        _probe_source(cases), encoding="utf-8"
    )
    manifest = project_root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8").replace(
        'entry = "src/lexer.mrt"', 'entry = "src/mir_parity_probe.mrt"'
    )
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), project_root


def _parse_probe_output(output: str, case_count: int):
    values = [int(value) for value in output.splitlines()]
    cursor = 0
    parsed = []
    for _ in range(case_count):
        assert cursor + 2 <= len(values)
        validation = values[cursor]
        count = values[cursor + 1]
        cursor += 2
        field_count = count * 11
        assert cursor + field_count <= len(values)
        fields = values[cursor : cursor + field_count]
        cursor += field_count
        parsed.append(
            (
                validation,
                [tuple(fields[index : index + 11]) for index in range(0, len(fields), 11)],
            )
        )
    assert cursor == len(values)
    return parsed


def _observations(cases, actual):
    observations = []
    for case, (validation, records) in zip(cases, actual, strict=True):
        assert validation == 0, case.case_id
        observations.extend(
            expression_mir_parity_observations(
                case.case_id,
                _reference_hir(case),
                records,
                case.text,
            )
        )
    return observations


def test_repository_primitive_expression_mir_has_real_interpreter_and_native_parity(tmp_path):
    corpus = load_repository_corpus(MANIFEST)
    cases = corpus.for_stage("mir")
    assert [case.case_id for case in cases] == [
        "precedence-product",
        "explicit-group",
        "left-associative-subtract",
        "comparison-last",
        "division-before-addition",
    ]
    project, project_root = _project_with_probe(tmp_path, cases)

    interpreted = _parse_probe_output(interpret(project), len(cases))
    interpreted_report = build_parity_report(
        corpus, _observations(cases, interpreted), stages=["mir"]
    )
    assert interpreted_report.complete, markdown_summary(interpreted_report)
    assert interpreted_report.stage_counts() == {"mir": (5, 5)}

    _, _, executable = build(project, project_root / "mir_parity")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native = _parse_probe_output(native_output, len(cases))
    assert native == interpreted

    native_report = build_parity_report(
        corpus, _observations(cases, native), stages=["mir"]
    )
    assert native_report.complete, markdown_summary(native_report)
    assert native_report.stage_counts() == {"mir": (5, 5)}
