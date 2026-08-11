from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.ast_contract import lower_expression_ast
from merit.bootstrap.corpus import BootstrapCorpus
from merit.bootstrap.hir_contract import HirType
from merit.bootstrap.hir_expression import (
    HirConstructorSignature,
    HirFieldSignature,
    HirFunctionSignature,
    lower_resolved_expression_hir,
)
from merit.bootstrap.mir_composite_parity import composite_mir_parity_observations
from merit.bootstrap.mir_contract import MirType
from merit.bootstrap.parity import build_parity_report, markdown_summary
from merit.bootstrap.repository_corpus import load_repository_corpus
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
MANIFEST = ROOT / "tests/project/bootstrap_corpus_v1.json"
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")
I64 = HirType("i64")
ACCOUNT = HirType("Account")
RECORD = HirType("Record")
POINT = HirType("Point")

CASE_IDS = (
    "empty-call",
    "argument-sequence",
    "field-before-addition",
    "nested-call-field",
    "direct-constructor-field",
)


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_mir_composite_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()


def _case_semantics(case_id: str):
    bindings: tuple[tuple[str, HirType], ...] = ()
    functions: tuple[HirFunctionSignature, ...] = ()
    fields: tuple[HirFieldSignature, ...] = ()
    constructors: tuple[HirConstructorSignature, ...] = ()
    type_names: dict[int, MirType] = {}
    case_kind = 0

    if case_id == "empty-call":
        functions = (HirFunctionSignature("f", (), I64),)
        case_kind = 1
    elif case_id == "argument-sequence":
        functions = (HirFunctionSignature("f", (I64, I64), I64),)
        case_kind = 2
    elif case_id == "field-before-addition":
        bindings = (("account", ACCOUNT),)
        fields = (HirFieldSignature(ACCOUNT, "balance", I64),)
        type_names = {3: MirType("Account")}
        case_kind = 3
    elif case_id == "nested-call-field":
        functions = (
            HirFunctionSignature("g", (I64,), I64),
            HirFunctionSignature("f", (I64,), RECORD),
        )
        fields = (HirFieldSignature(RECORD, "value", I64),)
        type_names = {4: MirType("Record")}
        case_kind = 4
    elif case_id == "direct-constructor-field":
        constructors = (
            HirConstructorSignature("Point", POINT, (("x", I64), ("y", I64))),
        )
        fields = (HirFieldSignature(POINT, "x", I64),)
        type_names = {5: MirType("Point")}
        case_kind = 5
    else:
        raise AssertionError(case_id)

    return bindings, functions, fields, constructors, type_names, case_kind


def _reference_hir(case):
    ast = lower_expression_ast(REFERENCE.reference_expression(case.text))
    bindings, functions, fields, constructors, _, _ = _case_semantics(case.case_id)
    return lower_resolved_expression_hir(
        ast,
        case.text,
        expected_type=I64,
        bindings=bindings,
        functions=functions,
        fields=fields,
        constructors=constructors,
        module_name=case.case_id,
    )


def _probe_source(cases) -> str:
    declarations: list[str] = []
    executions: list[str] = []
    for index, case in enumerate(cases):
        *_, case_kind = _case_semantics(case.case_id)
        declarations.append(
            f"        let source_{index}: Buffer = buffer_from_string(allocator, {json.dumps(case.text)});"
        )
        executions.append(
            f"        emit_composite_case(source_{index}, allocator, {case_kind});\n"
            f"        drop(source_{index});"
        )
    body = "\n".join(declarations + executions)
    return f'''module bootstrap_mir_composite_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_hir;
import bootstrap_mir_composite;

capability allocate;

fn ast_identifier_is_symbol(borrow ast_nodes: Vec<AstNodeRecord>, index: i64) -> i32 {{
    var parent_index: i64 = 0;
    while (parent_index < vec_len<AstNodeRecord>(ast_nodes)) {{
        let parent: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, parent_index);
        if (ast_kind(parent) == 34) {{ if (ast_left(parent) == index) {{ return 1; }} }}
        if (ast_kind(parent) == 35) {{ if (ast_right(parent) == index) {{ return 1; }} }}
        if (ast_kind(parent) == 38) {{ if (ast_left(parent) == index) {{ return 1; }} }}
        if (ast_kind(parent) == 70) {{ if (ast_left(parent) == index) {{ return 1; }} }}
        parent_index = checked_add(parent_index, 1);
    }}
    return 0;
}}

fn resolved_hir_type_code(
    borrow ast_nodes: Vec<AstNodeRecord>, index: i64, case_kind: i32
) -> i32 {{
    let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, index);
    if (ast_group_parent(ast) >= 0) {{ return 1; }}
    if (ast_kind(ast) == 37) {{ return 0; }}
    if (ast_kind(ast) == 38) {{ return 0; }}
    if (ast_kind(ast) == 30) {{
        if (ast_identifier_is_symbol(ast_nodes, index)) {{ return 0; }}
        if (case_kind == 3) {{ return 3; }}
        return 1;
    }}
    if (ast_kind(ast) == 34) {{
        if (case_kind == 4) {{
            let callee: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_left(ast));
            if (ast_start(callee) == 0) {{ return 4; }}
        }}
        return 1;
    }}
    if (ast_kind(ast) == 70) {{ if (case_kind == 5) {{ return 5; }} }}
    if (ast_kind(ast) == 35) {{ return 1; }}
    if (ast_kind(ast) >= 40) {{ if (ast_kind(ast) <= 45) {{ return 2; }} }}
    return 1;
}}

fn emit_composite_case(borrow source: Buffer, allocator: Allocator, case_kind: i32) -> i32
requires_caps [allocate]
{{
    let tokens: Vec<Token> = lex(source, allocator);
    let expressions: Vec<ExpressionNode> = parse_expression_tokens(source, tokens, allocator);
    let ast_nodes: Vec<AstNodeRecord> = lower_expression_ast_records(expressions, allocator);
    var hir_nodes: Vec<HirExpressionRecord> = vec_new<HirExpressionRecord>(
        allocator, vec_len<AstNodeRecord>(ast_nodes)
    );
    var binding_starts: Vec<i64> = vec_new<i64>(allocator, 4);
    var binding_lengths: Vec<i64> = vec_new<i64>(allocator, 4);
    var ast_index: i64 = 0;
    while (ast_index < vec_len<AstNodeRecord>(ast_nodes)) {{
        let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_index);
        var binding_id: i64 = -1;
        if (ast_kind(ast) == 30) {{
            if (ast_group_parent(ast) < 0) {{
                if (ast_identifier_is_symbol(ast_nodes, ast_index)) {{
                    binding_id = -2;
                }} else {{
                    binding_id = hir_find_binding_id(
                        source, binding_starts, binding_lengths,
                        ast_start(ast), ast_length(ast)
                    );
                    if (binding_id < 0) {{
                        binding_id = vec_len<i64>(binding_starts);
                        vec_push<i64>(binding_starts, ast_start(ast));
                        vec_push<i64>(binding_lengths, ast_length(ast));
                    }}
                }}
            }}
        }}
        let hir: HirExpressionRecord = lower_resolved_hir_record(
            ast_kind(ast), ast_start(ast), ast_length(ast),
            ast_left(ast), ast_right(ast), ast_group_start(ast), ast_group_length(ast),
            ast_group_parent(ast), binding_id,
            resolved_hir_type_code(ast_nodes, ast_index, case_kind)
        );
        vec_push<HirExpressionRecord>(hir_nodes, hir);
        ast_index = checked_add(ast_index, 1);
    }}

    let hir_validation: i32 = validate_primitive_hir_records(hir_nodes);
    let hir_count: i64 = vec_len<HirExpressionRecord>(hir_nodes);
    let binding_count: i64 = vec_len<i64>(binding_starts);
    var local_ids: Vec<i64> = vec_new<i64>(allocator, hir_count);
    var canonical_ids: Vec<i64> = vec_new<i64>(allocator, hir_count);
    var initialize_index: i64 = 0;
    while (initialize_index < hir_count) {{
        vec_push<i64>(local_ids, -1);
        vec_push<i64>(canonical_ids, -1);
        initialize_index = checked_add(initialize_index, 1);
    }}

    // Canonical HIR IDs are postorder and structural records consume no identity.
    var next_hir_id: i64 = 0;
    var canonical_index: i64 = 0;
    while (canonical_index < hir_count) {{
        let current: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, canonical_index);
        if (hir_kind(current) == 3) {{
            vec_set<i64>(canonical_ids, canonical_index, vec_get<i64>(canonical_ids, hir_left(current)));
        }} else {{
            if (hir_kind(current) != 8) {{
                if (hir_kind(current) != 9) {{
                    if (hir_kind(current) != 11) {{
                        vec_set<i64>(canonical_ids, canonical_index, next_hir_id);
                        next_hir_id = checked_add(next_hir_id, 1);
                    }}
                }}
            }}
        }}
        canonical_index = checked_add(canonical_index, 1);
    }}

    // Allocate MIR temporaries root-first while traversing HIR structural records.
    var stack: Vec<i64> = vec_new<i64>(allocator, hir_count);
    vec_push<i64>(stack, checked_sub(hir_count, 1));
    var next_temporary: i64 = binding_count;
    while (vec_len<i64>(stack) > 0) {{
        let current_index: i64 = vec_pop<i64>(stack);
        let current: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, current_index);
        let kind: i32 = hir_kind(current);
        if (kind == 8) {{
            vec_push<i64>(stack, hir_right(current));
            vec_push<i64>(stack, hir_left(current));
        }} else {{
            if (kind == 11) {{
                vec_push<i64>(stack, hir_right(current));
            }} else {{
                if (kind == 9) {{
                }} else {{
                    if (kind == 3) {{
                        vec_push<i64>(stack, hir_left(current));
                    }} else {{
                        if (kind == 4) {{
                            vec_set<i64>(local_ids, current_index, hir_binding_id(current));
                        }} else {{
                            if (vec_get<i64>(local_ids, current_index) < 0) {{
                                vec_set<i64>(local_ids, current_index, next_temporary);
                                next_temporary = checked_add(next_temporary, 1);
                            }}
                            if (kind == 2) {{
                                vec_push<i64>(stack, hir_right(current));
                                vec_push<i64>(stack, hir_left(current));
                            }}
                            if (kind == 5) {{
                                vec_push<i64>(stack, hir_right(current));
                                vec_push<i64>(stack, hir_left(current));
                            }}
                            if (kind == 6) {{
                                if (hir_right(current) >= 0) {{ vec_push<i64>(stack, hir_right(current)); }}
                            }}
                            if (kind == 7) {{ vec_push<i64>(stack, hir_left(current)); }}
                            if (kind == 10) {{
                                if (hir_right(current) >= 0) {{ vec_push<i64>(stack, hir_right(current)); }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}

    var mir_nodes: Vec<MirCompositeRecord> = vec_new<MirCompositeRecord>(allocator, hir_count);
    var hir_index: i64 = 0;
    while (hir_index < hir_count) {{
        let hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, hir_index);
        let kind: i32 = hir_kind(hir);
        let canonical_id: i64 = vec_get<i64>(canonical_ids, hir_index);
        let result_local: i64 = vec_get<i64>(local_ids, hir_index);
        if (kind == 1) {{
            vec_push<MirCompositeRecord>(mir_nodes, composite_const(
                hir_start(hir), hir_length(hir), result_local, hir_type_code(hir), canonical_id
            ));
        }}
        if (kind == 2) {{
            vec_push<MirCompositeRecord>(mir_nodes, composite_binary(
                hir_start(hir), hir_length(hir), result_local,
                vec_get<i64>(local_ids, hir_left(hir)), vec_get<i64>(local_ids, hir_right(hir)),
                hir_symbol(hir), hir_type_code(hir), hir_numeric_policy(hir), canonical_id
            ));
        }}
        if (kind == 4) {{
            vec_push<MirCompositeRecord>(mir_nodes, composite_binding(
                hir_start(hir), hir_length(hir), hir_binding_id(hir), hir_type_code(hir), canonical_id
            ));
        }}
        if (kind == 5) {{
            vec_push<MirCompositeRecord>(mir_nodes, composite_binary(
                hir_start(hir), hir_length(hir), result_local,
                vec_get<i64>(local_ids, hir_left(hir)), vec_get<i64>(local_ids, hir_right(hir)),
                hir_symbol(hir), hir_type_code(hir), hir_numeric_policy(hir), canonical_id
            ));
        }}
        if (kind == 6) {{
            if (hir_right(hir) >= 0) {{
                var operand_stack: Vec<i64> = vec_new<i64>(allocator, hir_count);
                vec_push<i64>(operand_stack, hir_right(hir));
                var ordinal: i64 = 0;
                while (vec_len<i64>(operand_stack) > 0) {{
                    let operand_index: i64 = vec_pop<i64>(operand_stack);
                    let operand_hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, operand_index);
                    if (hir_kind(operand_hir) == 8) {{
                        vec_push<i64>(operand_stack, hir_right(operand_hir));
                        vec_push<i64>(operand_stack, hir_left(operand_hir));
                    }} else {{
                        vec_push<MirCompositeRecord>(mir_nodes, composite_operand(
                            vec_get<i64>(local_ids, operand_index), canonical_id, ordinal
                        ));
                        ordinal = checked_add(ordinal, 1);
                    }}
                }}
                drop(operand_stack);
            }}
            let symbol_hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, hir_left(hir));
            vec_push<MirCompositeRecord>(mir_nodes, composite_call(
                hir_start(hir), hir_length(hir), result_local,
                hir_start(symbol_hir), hir_length(symbol_hir), hir_type_code(hir), canonical_id
            ));
        }}
        if (kind == 7) {{
            let symbol_hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, hir_right(hir));
            vec_push<MirCompositeRecord>(mir_nodes, composite_field(
                hir_start(hir), hir_length(hir), result_local,
                vec_get<i64>(local_ids, hir_left(hir)),
                hir_start(symbol_hir), hir_length(symbol_hir), hir_type_code(hir), canonical_id
            ));
        }}
        if (kind == 10) {{
            if (hir_right(hir) >= 0) {{
                var initializer_stack: Vec<i64> = vec_new<i64>(allocator, hir_count);
                vec_push<i64>(initializer_stack, hir_right(hir));
                var ordinal: i64 = 0;
                while (vec_len<i64>(initializer_stack) > 0) {{
                    let initializer_index: i64 = vec_pop<i64>(initializer_stack);
                    let initializer_hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, initializer_index);
                    if (hir_kind(initializer_hir) == 8) {{
                        vec_push<i64>(initializer_stack, hir_right(initializer_hir));
                        vec_push<i64>(initializer_stack, hir_left(initializer_hir));
                    }} else {{
                        if (hir_kind(initializer_hir) == 11) {{
                            vec_push<MirCompositeRecord>(mir_nodes, composite_operand(
                                vec_get<i64>(local_ids, hir_right(initializer_hir)), canonical_id, ordinal
                            ));
                            ordinal = checked_add(ordinal, 1);
                        }}
                    }}
                }}
                drop(initializer_stack);
            }}
            let symbol_hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, hir_left(hir));
            vec_push<MirCompositeRecord>(mir_nodes, composite_construct(
                hir_start(hir), hir_length(hir), result_local,
                hir_start(symbol_hir), hir_length(symbol_hir), hir_type_code(hir), canonical_id
            ));
        }}
        hir_index = checked_add(hir_index, 1);
    }}

    let mir_validation: i32 = validate_composite_mir_records(mir_nodes);
    if (hir_validation != 0) {{ print(checked_add(90, hir_validation)); }} else {{ print(mir_validation); }}
    print(vec_len<MirCompositeRecord>(mir_nodes));
    var output_index: i64 = 0;
    while (output_index < vec_len<MirCompositeRecord>(mir_nodes)) {{
        let node: MirCompositeRecord = vec_get<MirCompositeRecord>(mir_nodes, output_index);
        print(composite_kind(node)); print(composite_start(node)); print(composite_length(node));
        print(composite_result(node)); print(composite_left(node)); print(composite_right(node));
        print(composite_symbol_start(node)); print(composite_symbol_length(node));
        print(composite_symbol_code(node)); print(composite_type_code(node));
        print(composite_numeric_policy(node)); print(composite_binding_id(node));
        print(composite_hir_node_id(node)); print(composite_owner_hir_id(node));
        print(composite_ordinal(node));
        output_index = checked_add(output_index, 1);
    }}

    drop(mir_nodes); drop(stack); drop(canonical_ids); drop(local_ids);
    drop(binding_lengths); drop(binding_starts); drop(hir_nodes); drop(ast_nodes);
    drop(expressions); drop(tokens);
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
    project_root = tmp_path / "bootstrap_mir_composite_parity"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (project_root / "src/mir_composite_probe.mrt").write_text(
        _probe_source(cases), encoding="utf-8"
    )
    manifest = project_root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8").replace(
        'entry = "src/lexer.mrt"', 'entry = "src/mir_composite_probe.mrt"'
    )
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), project_root


def _parse_probe_output(output: str, case_count: int):
    values = [int(value) for value in output.splitlines()]
    cursor = 0
    parsed = []
    for _ in range(case_count):
        validation = values[cursor]
        count = values[cursor + 1]
        cursor += 2
        field_count = count * 15
        fields = values[cursor : cursor + field_count]
        cursor += field_count
        parsed.append(
            (
                validation,
                [tuple(fields[index : index + 15]) for index in range(0, len(fields), 15)],
            )
        )
    assert cursor == len(values)
    return parsed


def _observations(cases, actual):
    observations = []
    for case, (validation, records) in zip(cases, actual, strict=True):
        assert validation == 0, case.case_id
        *_, type_names, _ = _case_semantics(case.case_id)
        observations.extend(
            composite_mir_parity_observations(
                case.case_id,
                _reference_hir(case),
                records,
                case.text,
                type_names=type_names,
            )
        )
    return observations


def test_repository_composite_expression_mir_has_real_interpreter_and_native_parity(tmp_path):
    corpus = load_repository_corpus(MANIFEST)
    cases = tuple(corpus.by_id(case_id) for case_id in CASE_IDS)
    subset = BootstrapCorpus(corpus.schema, cases)
    project, project_root = _project_with_probe(tmp_path, cases)

    interpreted = _parse_probe_output(interpret(project), len(cases))
    interpreted_report = build_parity_report(
        subset, _observations(cases, interpreted), stages=["mir"]
    )
    assert interpreted_report.complete, markdown_summary(interpreted_report)
    assert interpreted_report.stage_counts() == {"mir": (5, 5)}

    _, _, executable = build(project, project_root / "mir_composite_parity")
    native = _parse_probe_output(
        subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout,
        len(cases),
    )
    assert native == interpreted
    native_report = build_parity_report(
        subset, _observations(cases, native), stages=["mir"]
    )
    assert native_report.complete, markdown_summary(native_report)
    assert native_report.stage_counts() == {"mir": (5, 5)}
