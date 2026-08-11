from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.ast_contract import lower_expression_ast
from merit.bootstrap.corpus import BootstrapCorpus
from merit.bootstrap.hir_contract import HirType
from merit.bootstrap.hir_expression import HirFunctionSignature, lower_resolved_expression_hir
from merit.bootstrap.mir_contract import MirType
from merit.bootstrap.mir_generic_parity import generic_mir_parity_observations
from merit.bootstrap.parity import build_parity_report, markdown_summary
from merit.bootstrap.repository_corpus import load_repository_corpus
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
MANIFEST = ROOT / "tests/project/bootstrap_corpus_v1.json"
REFERENCE_PATH = Path(__file__).with_name("test_bootstrap_lexer.py")
I64 = HirType("i64")
TYPE_T = HirType("T")
CASE_ID = "single-generic-call"


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_mir_generic_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()


def _reference_hir(case):
    ast = lower_expression_ast(REFERENCE.reference_expression(case.text))
    return lower_resolved_expression_hir(
        ast,
        case.text,
        expected_type=I64,
        functions=(HirFunctionSignature("identity", (TYPE_T,), TYPE_T, ("T",)),),
        generic_types={"i64": I64},
        module_name=case.case_id,
    )


def _probe_source(source: str) -> str:
    escaped = source.replace("\\", "\\\\").replace('"', '\\"')
    return f'''module bootstrap_mir_generic_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_hir;
import bootstrap_hir_generics;
import bootstrap_mir_generics;

capability allocate;

fn emit_case(borrow source: Buffer, allocator: Allocator) -> i32
requires_caps [allocate]
{{
    let tokens: Vec<Token> = lex(source, allocator);
    let expressions: Vec<ExpressionNode> = parse_expression_tokens(source, tokens, allocator);
    let ast_nodes: Vec<AstNodeRecord> = lower_expression_ast_records(expressions, allocator);

    var literal_index: i64 = -1;
    var generic_index: i64 = -1;
    var call_index: i64 = -1;
    var index: i64 = 0;
    while (index < vec_len<AstNodeRecord>(ast_nodes)) {{
        let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, index);
        if (ast_kind(ast) == 31) {{ literal_index = index; }}
        if (ast_kind(ast) == 36) {{ generic_index = index; }}
        if (ast_kind(ast) == 34) {{ call_index = index; }}
        index = checked_add(index, 1);
    }}

    var records: Vec<MirGenericRecord> = vec_new<MirGenericRecord>(allocator, 3);
    if (literal_index >= 0) {{
        if (generic_index >= 0) {{
            if (call_index >= 0) {{
                let literal_ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, literal_index);
                let generic_ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, generic_index);
                let call_ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, call_index);
                let generic_hir: HirExpressionRecord = lower_generic_apply_hir_record(
                    ast_start(generic_ast), ast_length(generic_ast)
                );
                let literal_hir: HirExpressionRecord = lower_resolved_hir_record(
                    ast_kind(literal_ast), ast_start(literal_ast), ast_length(literal_ast),
                    ast_left(literal_ast), ast_right(literal_ast),
                    ast_group_start(literal_ast), ast_group_length(literal_ast),
                    ast_group_parent(literal_ast), -1, 1
                );
                let call_hir: HirExpressionRecord = lower_resolved_hir_record(
                    ast_kind(call_ast), ast_start(call_ast), ast_length(call_ast),
                    ast_left(call_ast), ast_right(call_ast),
                    ast_group_start(call_ast), ast_group_length(call_ast),
                    ast_group_parent(call_ast), -1, 1
                );
                if (hir_kind(generic_hir) == 9) {{
                    if (hir_kind(literal_hir) == 1) {{
                        if (hir_kind(call_hir) == 6) {{
                            let base_ast: AstNodeRecord = vec_get<AstNodeRecord>(
                                ast_nodes, ast_left(generic_ast)
                            );
                            vec_push<MirGenericRecord>(records, generic_const(
                                hir_start(literal_hir), hir_length(literal_hir), 1, 1, 0
                            ));
                            vec_push<MirGenericRecord>(records, generic_operand_marker(1, 1, 0));
                            vec_push<MirGenericRecord>(records, generic_call(
                                hir_start(call_hir), hir_length(call_hir), 0,
                                ast_start(base_ast), ast_length(base_ast), 1, 1, 1
                            ));
                        }}
                    }}
                }}
            }}
        }}
    }}

    print(validate_generic_mir_records(records));
    print(vec_len<MirGenericRecord>(records));
    index = 0;
    while (index < vec_len<MirGenericRecord>(records)) {{
        let node: MirGenericRecord = vec_get<MirGenericRecord>(records, index);
        print(generic_kind(node)); print(generic_start(node)); print(generic_length(node));
        print(generic_result(node)); print(generic_operand(node));
        print(generic_symbol_start(node)); print(generic_symbol_length(node));
        print(generic_type_code(node)); print(generic_specialization_type_code(node));
        print(generic_hir_node_id(node)); print(generic_owner_hir_id(node));
        print(generic_ordinal(node));
        index = checked_add(index, 1);
    }}

    drop(records); drop(ast_nodes); drop(expressions); drop(tokens);
    return 0;
}}

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "{escaped}");
        emit_case(source, allocator);
        drop(source);
    }}
    return 0;
}}
'''


def _project_with_probe(tmp_path: Path, source: str):
    project_root = tmp_path / "bootstrap_mir_generic_parity"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (project_root / "src/mir_generic_probe.mrt").write_text(
        _probe_source(source), encoding="utf-8"
    )
    manifest = project_root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8").replace(
        'entry = "src/lexer.mrt"', 'entry = "src/mir_generic_probe.mrt"'
    )
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), project_root


def _parse_output(output: str):
    values = [int(value) for value in output.splitlines()]
    validation, count = values[:2]
    fields = values[2:]
    assert len(fields) == count * 12
    return validation, [tuple(fields[index:index + 12]) for index in range(0, len(fields), 12)]


def _report(case, actual):
    validation, records = actual
    assert validation == 0
    observations = generic_mir_parity_observations(
        case.case_id,
        _reference_hir(case),
        records,
        case.text,
        type_names={1: MirType("i64")},
    )
    subset = BootstrapCorpus("bootstrap-corpus-v1", (case,))
    return build_parity_report(subset, observations, stages=["mir"])


def test_repository_generic_expression_mir_has_real_interpreter_and_native_parity(tmp_path):
    corpus = load_repository_corpus(MANIFEST)
    case = corpus.by_id(CASE_ID)
    project, project_root = _project_with_probe(tmp_path, case.text)

    interpreted = _parse_output(interpret(project))
    interpreted_report = _report(case, interpreted)
    assert interpreted_report.complete, markdown_summary(interpreted_report)
    assert interpreted_report.stage_counts() == {"mir": (1, 1)}

    _, _, executable = build(project, project_root / "mir_generic_parity")
    native = _parse_output(
        subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    )
    assert native == interpreted
    native_report = _report(case, native)
    assert native_report.complete, markdown_summary(native_report)
    assert native_report.stage_counts() == {"mir": (1, 1)}
