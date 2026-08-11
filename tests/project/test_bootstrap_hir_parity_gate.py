from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.ast_contract import lower_expression_ast
from merit.bootstrap.hir_contract import HirType
from merit.bootstrap.hir_expression import (
    HirConstructorSignature,
    HirFieldSignature,
    HirFunctionSignature,
    lower_resolved_expression_hir,
)
from merit.bootstrap.hir_string_parity import string_hir_parity_observations
from merit.bootstrap.parity import build_parity_report, markdown_summary
from merit.bootstrap.repository_corpus import load_repository_corpus
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
MANIFEST = ROOT / "tests/project/bootstrap_corpus_v1.json"
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")
I64 = HirType("i64")
STRING = HirType("string")
TYPE_T = HirType("T")
ACCOUNT = HirType("Account")
RECORD = HirType("Record")
POINT = HirType("Point")


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_hir_parity_reference", REFERENCE_PATH
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
    type_names: dict[int, HirType] = {}
    constructor_fields: dict[str, tuple[str, ...]] = {}
    generic_types: dict[str, HirType] = {}
    case_kind = 0

    if case_id == "left-associative-subtract":
        bindings = (("a", I64), ("b", I64), ("c", I64))
    elif case_id == "comparison-last":
        bindings = (("a", I64), ("b", I64))
    elif case_id == "string-atom":
        type_names = {6: STRING}
        case_kind = 7
    elif case_id == "division-before-addition":
        bindings = (("a", I64),)
    elif case_id == "empty-call":
        functions = (HirFunctionSignature("f", (), I64),)
        case_kind = 1
    elif case_id == "argument-sequence":
        functions = (HirFunctionSignature("f", (I64, I64), I64),)
        case_kind = 2
    elif case_id == "field-before-addition":
        bindings = (("account", ACCOUNT),)
        fields = (HirFieldSignature(ACCOUNT, "balance", I64),)
        type_names = {3: ACCOUNT}
        case_kind = 3
    elif case_id == "nested-call-field":
        functions = (
            HirFunctionSignature("g", (I64,), I64),
            HirFunctionSignature("f", (I64,), RECORD),
        )
        fields = (HirFieldSignature(RECORD, "value", I64),)
        type_names = {4: RECORD}
        case_kind = 4
    elif case_id == "direct-constructor-field":
        constructors = (
            HirConstructorSignature("Point", POINT, (("x", I64), ("y", I64))),
        )
        fields = (HirFieldSignature(POINT, "x", I64),)
        type_names = {5: POINT}
        constructor_fields = {"Point": ("x", "y")}
        case_kind = 5
    elif case_id == "single-generic-call":
        functions = (
            HirFunctionSignature("identity", (TYPE_T,), TYPE_T, ("T",)),
        )
        generic_types = {"i64": I64}
        case_kind = 6

    return (
        bindings,
        functions,
        fields,
        constructors,
        type_names,
        constructor_fields,
        generic_types,
        case_kind,
    )


def _probe_source(cases) -> str:
    declarations = []
    executions = []
    for index, case in enumerate(cases):
        _, _, _, _, _, _, _, case_kind = _case_semantics(case.case_id)
        literal = json.dumps(case.text)
        declarations.append(
            f"        let source_{index}: Buffer = buffer_from_string(allocator, {literal});"
        )
        executions.append(
            f"        emit_hir_case(source_{index}, allocator, {case_kind});\n"
            f"        drop(source_{index});"
        )
    body = "\n".join(declarations + executions)
    return f'''module bootstrap_hir_parity_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_hir;
import bootstrap_hir_generics;
import bootstrap_hir_strings;

capability allocate;

fn ast_identifier_is_symbol(borrow ast_nodes: Vec<AstNodeRecord>, index: i64) -> i32 {{
    var parent_index: i64 = 0;
    while (parent_index < vec_len<AstNodeRecord>(ast_nodes)) {{
        let parent: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, parent_index);
        if (ast_kind(parent) == 34) {{
            if (ast_left(parent) == index) {{ return 1; }}
        }}
        if (ast_kind(parent) == 35) {{
            if (ast_right(parent) == index) {{ return 1; }}
        }}
        if (ast_kind(parent) == 36) {{
            if (ast_left(parent) == index) {{ return 1; }}
            if (ast_right(parent) == index) {{ return 1; }}
        }}
        if (ast_kind(parent) == 38) {{
            if (ast_left(parent) == index) {{ return 1; }}
        }}
        if (ast_kind(parent) == 70) {{
            if (ast_left(parent) == index) {{ return 1; }}
        }}
        parent_index = checked_add(parent_index, 1);
    }}
    return 0;
}}

fn resolved_hir_type_code(
    borrow ast_nodes: Vec<AstNodeRecord>,
    index: i64,
    case_kind: i32
) -> i32 {{
    let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, index);
    if (ast_group_parent(ast) >= 0) {{ return 1; }}
    if (ast_kind(ast) == 32) {{
        if (case_kind == 7) {{ return 6; }}
    }}
    if (ast_kind(ast) == 36) {{ return 0; }}
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
    if (ast_kind(ast) == 70) {{
        if (case_kind == 5) {{ return 5; }}
    }}
    if (ast_kind(ast) == 35) {{ return 1; }}
    if (ast_kind(ast) == 40) {{ return 2; }}
    if (ast_kind(ast) == 41) {{ return 2; }}
    if (ast_kind(ast) == 42) {{ return 2; }}
    if (ast_kind(ast) == 43) {{ return 2; }}
    if (ast_kind(ast) == 44) {{ return 2; }}
    if (ast_kind(ast) == 45) {{ return 2; }}
    return 1;
}}

fn lower_probe_hir_record(
    borrow ast_nodes: Vec<AstNodeRecord>,
    ast_index: i64,
    binding_id: i64,
    case_kind: i32
) -> HirExpressionRecord
{{
    let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_index);
    if (ast_kind(ast) == 32) {{
        return lower_string_hir_record(
            ast_start(ast),
            ast_length(ast),
            resolved_hir_type_code(ast_nodes, ast_index, case_kind)
        );
    }}
    if (ast_kind(ast) == 36) {{
        return lower_generic_apply_hir_record(ast_start(ast), ast_length(ast));
    }}
    return lower_resolved_hir_record(
        ast_kind(ast),
        ast_start(ast),
        ast_length(ast),
        ast_left(ast),
        ast_right(ast),
        ast_group_start(ast),
        ast_group_length(ast),
        ast_group_parent(ast),
        binding_id,
        resolved_hir_type_code(ast_nodes, ast_index, case_kind)
    );
}}

fn validate_probe_hir_records(borrow nodes: Vec<HirExpressionRecord>, case_kind: i32) -> i32 {{
    if (case_kind == 7) {{
        if (vec_len<HirExpressionRecord>(nodes) != 1) {{ return 1; }}
        let node: HirExpressionRecord = vec_get<HirExpressionRecord>(nodes, 0);
        return validate_string_hir_record(node);
    }}
    return validate_primitive_hir_records(nodes);
}}

fn emit_hir_case(borrow source: Buffer, allocator: Allocator, case_kind: i32) -> i32
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
                if (ast_identifier_is_symbol(ast_nodes, ast_index)) {{
                    binding_id = -2;
                }} else {{
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
        }}
        let hir: HirExpressionRecord = lower_probe_hir_record(
            ast_nodes,
            ast_index,
            binding_id,
            case_kind
        );
        vec_push<HirExpressionRecord>(hir_nodes, hir);
        ast_index = checked_add(ast_index, 1);
    }}
    print(validate_probe_hir_records(hir_nodes, case_kind));
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


def _project_with_probe(tmp_path: Path, cases):
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
        _probe_source(cases), encoding="utf-8"
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
    (
        bindings,
        functions,
        fields,
        constructors,
        _,
        _,
        generic_types,
        _,
    ) = _case_semantics(case.case_id)
    expected_type = STRING if case.case_id == "string-atom" else I64
    return lower_resolved_expression_hir(
        ast,
        case.text,
        expected_type=expected_type,
        bindings=bindings,
        functions=functions,
        fields=fields,
        constructors=constructors,
        types=tuple(generic_types.values()),
        module_name=case.case_id,
    )


def _observations(cases, actual):
    observations = []
    for case, (validation, records) in zip(cases, actual, strict=True):
        assert validation == 0, case.case_id
        (
            _,
            _,
            _,
            _,
            type_names,
            constructor_fields,
            generic_types,
            _,
        ) = _case_semantics(case.case_id)
        observations.extend(
            string_hir_parity_observations(
                case.case_id,
                _reference_hir(case),
                records,
                case.text,
                type_names=type_names,
                constructor_fields=constructor_fields,
                generic_types=generic_types,
            )
        )
    return observations


def test_repository_resolved_expression_hir_has_real_interpreter_and_native_parity(tmp_path):
    corpus = load_repository_corpus(MANIFEST)
    cases = corpus.for_stage("hir")
    assert [case.case_id for case in cases] == [
        "precedence-product",
        "explicit-group",
        "left-associative-subtract",
        "comparison-last",
        "string-atom",
        "division-before-addition",
        "empty-call",
        "argument-sequence",
        "field-before-addition",
        "nested-call-field",
        "direct-constructor-field",
        "single-generic-call",
    ]
    project, project_root = _project_with_probe(tmp_path, cases)

    interpreted = _parse_probe_output(interpret(project), len(cases))
    interpreted_report = build_parity_report(
        corpus, _observations(cases, interpreted), stages=["hir"]
    )
    assert interpreted_report.complete, markdown_summary(interpreted_report)
    assert interpreted_report.stage_counts() == {"hir": (12, 12)}

    _, _, executable = build(project, project_root / "hir_parity")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native = _parse_probe_output(native_output, len(cases))
    native_report = build_parity_report(
        corpus, _observations(cases, native), stages=["hir"]
    )
    assert native_report.complete, markdown_summary(native_report)
    assert native_report.stage_counts() == {"hir": (12, 12)}

    assert native == interpreted
