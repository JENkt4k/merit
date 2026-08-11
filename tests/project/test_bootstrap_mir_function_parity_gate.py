from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType, SourceSpan
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.mir_contract import canonical_mir_json
from merit.bootstrap.mir_function_parity import lower_native_function_mir_records
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
SOURCE = "module demo\nfn compute()->i64 { let x:i64=1+2; var y:i64=x*3; return y+4; }\n"
I64 = HirType("i64")


def _reference_mir():
    bindings = (
        HirBinding(0, "x", I64),
        HirBinding(1, "y", I64, mutable=True),
    )
    nodes = (
        HirNode(0, "literal", I64, span=SourceSpan(42, 1), value="1", numeric_policy="exact"),
        HirNode(1, "literal", I64, span=SourceSpan(44, 1), value="2", numeric_policy="exact"),
        HirNode(2, "binary", I64, children=(0, 1), span=SourceSpan(42, 3), symbol="+", numeric_policy="checked"),
        HirNode(3, "let", I64, children=(2,), span=SourceSpan(32, 14), binding_id=0),
        HirNode(4, "identifier", I64, span=SourceSpan(57, 1), binding_id=0, ownership="value"),
        HirNode(5, "literal", I64, span=SourceSpan(59, 1), value="3", numeric_policy="exact"),
        HirNode(6, "binary", I64, children=(4, 5), span=SourceSpan(57, 3), symbol="*", numeric_policy="checked"),
        HirNode(7, "let", I64, children=(6,), span=SourceSpan(47, 14), binding_id=1),
        HirNode(8, "identifier", I64, span=SourceSpan(69, 1), binding_id=1, ownership="value"),
        HirNode(9, "literal", I64, span=SourceSpan(71, 1), value="4", numeric_policy="exact"),
        HirNode(10, "binary", I64, children=(8, 9), span=SourceSpan(69, 3), symbol="+", numeric_policy="checked"),
        HirNode(11, "return", I64, children=(10,), span=SourceSpan(62, 11)),
        HirNode(12, "function", I64, children=(3, 7, 11), symbol="compute"),
    )
    return lower_hir_to_mir(HirModule("demo", bindings, nodes, (12,)))


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module bootstrap_mir_function_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_expression_spans;
import bootstrap_hir;
import bootstrap_mir_functions;

capability allocate;

fn probe_byte(borrow source: Buffer, borrow token: Token, offset: i64) -> i64 {{
    return buffer_get(source, checked_add(token_start(token), offset));
}}

fn probe_is_fn(borrow source: Buffer, borrow token: Token) -> i32 {{
    if (token_kind(token) != 1) {{ return 0; }}
    if (token_length(token) != 2) {{ return 0; }}
    if (probe_byte(source, token, 0) != 102) {{ return 0; }}
    if (probe_byte(source, token, 1) != 110) {{ return 0; }}
    return 1;
}}

fn probe_function_name_index(borrow source: Buffer, borrow tokens: Vec<Token>) -> i64 {{
    var index: i64 = 0;
    while (index < vec_len<Token>(tokens)) {{
        let token: Token = vec_get<Token>(tokens, index);
        if (probe_is_fn(source, token)) {{
            let name_index: i64 = checked_add(index, 1);
            if (name_index < vec_len<Token>(tokens)) {{ return name_index; }}
        }}
        index = checked_add(index, 1);
    }}
    return -1;
}}

fn probe_expression_operand(
    borrow statement: StatementRecord,
    borrow operands: Vec<StatementOperand>
) -> i64 {{
    var offset: i64 = 0;
    while (offset < statement_record_operand_count(statement)) {{
        let index: i64 = checked_add(statement_record_first_operand(statement), offset);
        let operand: StatementOperand = vec_get<StatementOperand>(operands, index);
        if (statement_operand_kind(operand) == 3) {{ return index; }}
        offset = checked_add(offset, 1);
    }}
    return -1;
}}

fn probe_binding_operand(
    borrow statement: StatementRecord,
    borrow operands: Vec<StatementOperand>
) -> i64 {{
    var offset: i64 = 0;
    while (offset < statement_record_operand_count(statement)) {{
        let index: i64 = checked_add(statement_record_first_operand(statement), offset);
        let operand: StatementOperand = vec_get<StatementOperand>(operands, index);
        if (statement_operand_kind(operand) == 1) {{ return index; }}
        offset = checked_add(offset, 1);
    }}
    return -1;
}}

fn probe_emit_expression(
    borrow source: Buffer,
    borrow tokens: Vec<Token>,
    borrow binding_starts: Vec<i64>,
    borrow binding_lengths: Vec<i64>,
    expression_start: i64,
    expression_length: i64,
    allocator: Allocator,
    borrow_mut output: Vec<MirFunctionRecord>,
    borrow_mut counters: Vec<i64>
) -> i64
requires_caps [allocate]
{{
    let expressions: Vec<ExpressionNode> = parse_expression_span(
        source, tokens, expression_start, expression_length, allocator
    );
    let ast_nodes: Vec<AstNodeRecord> = lower_expression_ast_records(expressions, allocator);
    let count: i64 = vec_len<AstNodeRecord>(ast_nodes);
    var hir_nodes: Vec<HirExpressionRecord> = vec_new<HirExpressionRecord>(allocator, count);
    var ast_index: i64 = 0;
    while (ast_index < count) {{
        let ast: AstNodeRecord = vec_get<AstNodeRecord>(ast_nodes, ast_index);
        var binding_id: i64 = -1;
        if (ast_kind(ast) == 30) {{
            binding_id = hir_find_binding_id(
                source, binding_starts, binding_lengths, ast_start(ast), ast_length(ast)
            );
        }}
        let hir: HirExpressionRecord = lower_resolved_hir_record(
            ast_kind(ast), ast_start(ast), ast_length(ast), ast_left(ast), ast_right(ast),
            ast_group_start(ast), ast_group_length(ast), ast_group_parent(ast), binding_id, 1
        );
        vec_push<HirExpressionRecord>(hir_nodes, hir);
        ast_index = checked_add(ast_index, 1);
    }}

    var canonical_ids: Vec<i64> = vec_new<i64>(allocator, count);
    var local_ids: Vec<i64> = vec_new<i64>(allocator, count);
    var initialize: i64 = 0;
    while (initialize < count) {{
        vec_push<i64>(canonical_ids, -1);
        vec_push<i64>(local_ids, -1);
        initialize = checked_add(initialize, 1);
    }}

    var next_hir: i64 = vec_get<i64>(counters, 2);
    var canonical_index: i64 = 0;
    while (canonical_index < count) {{
        let hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, canonical_index);
        if (hir_kind(hir) == 3) {{
            vec_set<i64>(canonical_ids, canonical_index, vec_get<i64>(canonical_ids, hir_left(hir)));
        }} else {{
            vec_set<i64>(canonical_ids, canonical_index, next_hir);
            next_hir = checked_add(next_hir, 1);
        }}
        canonical_index = checked_add(canonical_index, 1);
    }}
    vec_set<i64>(counters, 2, next_hir);

    var stack: Vec<i64> = vec_new<i64>(allocator, count);
    vec_push<i64>(stack, checked_sub(count, 1));
    while (vec_len<i64>(stack) > 0) {{
        let current_index: i64 = vec_pop<i64>(stack);
        let hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, current_index);
        let kind: i32 = hir_kind(hir);
        if (kind == 3) {{
            vec_push<i64>(stack, hir_left(hir));
        }} else {{
            if (kind == 4) {{
                vec_set<i64>(local_ids, current_index, hir_binding_id(hir));
            }} else {{
                if (vec_get<i64>(local_ids, current_index) < 0) {{
                    let next_local: i64 = vec_get<i64>(counters, 0);
                    vec_set<i64>(local_ids, current_index, next_local);
                    vec_push<MirFunctionRecord>(output, function_mir_temporary(
                        next_local, hir_type_code(hir), vec_get<i64>(canonical_ids, current_index)
                    ));
                    vec_set<i64>(counters, 0, checked_add(next_local, 1));
                }}
                if (kind == 2) {{
                    vec_push<i64>(stack, hir_right(hir));
                    vec_push<i64>(stack, hir_left(hir));
                }}
                if (kind == 5) {{
                    vec_push<i64>(stack, hir_right(hir));
                    vec_push<i64>(stack, hir_left(hir));
                }}
            }}
        }}
    }}

    var hir_index: i64 = 0;
    while (hir_index < count) {{
        let hir: HirExpressionRecord = vec_get<HirExpressionRecord>(hir_nodes, hir_index);
        let kind: i32 = hir_kind(hir);
        if (kind == 1) {{
            let instruction_id: i64 = vec_get<i64>(counters, 1);
            vec_push<MirFunctionRecord>(output, function_mir_const(
                hir_start(hir), hir_length(hir), instruction_id,
                vec_get<i64>(local_ids, hir_index), hir_type_code(hir),
                vec_get<i64>(canonical_ids, hir_index)
            ));
            vec_set<i64>(counters, 1, checked_add(instruction_id, 1));
        }}
        if (kind == 2) {{
            let instruction_id: i64 = vec_get<i64>(counters, 1);
            vec_push<MirFunctionRecord>(output, function_mir_binary(
                hir_start(hir), hir_length(hir), instruction_id,
                vec_get<i64>(local_ids, hir_index),
                vec_get<i64>(local_ids, hir_left(hir)), vec_get<i64>(local_ids, hir_right(hir)),
                hir_symbol(hir), hir_type_code(hir), hir_numeric_policy(hir),
                vec_get<i64>(canonical_ids, hir_index)
            ));
            vec_set<i64>(counters, 1, checked_add(instruction_id, 1));
        }}
        if (kind == 5) {{
            let instruction_id: i64 = vec_get<i64>(counters, 1);
            vec_push<MirFunctionRecord>(output, function_mir_binary(
                hir_start(hir), hir_length(hir), instruction_id,
                vec_get<i64>(local_ids, hir_index),
                vec_get<i64>(local_ids, hir_left(hir)), vec_get<i64>(local_ids, hir_right(hir)),
                hir_symbol(hir), hir_type_code(hir), hir_numeric_policy(hir),
                vec_get<i64>(canonical_ids, hir_index)
            ));
            vec_set<i64>(counters, 1, checked_add(instruction_id, 1));
        }}
        hir_index = checked_add(hir_index, 1);
    }}

    let result_local: i64 = vec_get<i64>(local_ids, checked_sub(count, 1));
    drop(stack); drop(local_ids); drop(canonical_ids); drop(hir_nodes); drop(ast_nodes); drop(expressions);
    return result_local;
}}

fn emit_function(borrow source: Buffer, allocator: Allocator) -> i32
requires_caps [allocate]
{{
    let tokens: Vec<Token> = lex(source, allocator);
    let statements: Vec<StatementRecord> = parse_statement_records(source, tokens, allocator);
    let operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);
    var output: Vec<MirFunctionRecord> = vec_new<MirFunctionRecord>(allocator, 32);
    var binding_starts: Vec<i64> = vec_new<i64>(allocator, 8);
    var binding_lengths: Vec<i64> = vec_new<i64>(allocator, 8);

    let name_index: i64 = probe_function_name_index(source, tokens);
    let name_token: Token = vec_get<Token>(tokens, name_index);
    vec_push<MirFunctionRecord>(output, function_mir_header(
        token_start(name_token), token_length(name_token),
        token_start(name_token), token_length(name_token), 1
    ));

    var statement_index: i64 = 0;
    while (statement_index < vec_len<StatementRecord>(statements)) {{
        let statement: StatementRecord = vec_get<StatementRecord>(statements, statement_index);
        let kind: i32 = statement_record_kind(statement);
        if (kind == 20) {{
            let binding_operand_index: i64 = probe_binding_operand(statement, operands);
            let binding_operand: StatementOperand = vec_get<StatementOperand>(operands, binding_operand_index);
            let binding_id: i64 = vec_len<i64>(binding_starts);
            vec_push<i64>(binding_starts, statement_operand_start(binding_operand));
            vec_push<i64>(binding_lengths, statement_operand_length(binding_operand));
            vec_push<MirFunctionRecord>(output, function_mir_source_local(
                statement_operand_start(binding_operand), statement_operand_length(binding_operand),
                binding_id, 1, binding_id, 0
            ));
        }}
        if (kind == 21) {{
            let binding_operand_index: i64 = probe_binding_operand(statement, operands);
            let binding_operand: StatementOperand = vec_get<StatementOperand>(operands, binding_operand_index);
            let binding_id: i64 = vec_len<i64>(binding_starts);
            vec_push<i64>(binding_starts, statement_operand_start(binding_operand));
            vec_push<i64>(binding_lengths, statement_operand_length(binding_operand));
            vec_push<MirFunctionRecord>(output, function_mir_source_local(
                statement_operand_start(binding_operand), statement_operand_length(binding_operand),
                binding_id, 1, binding_id, 1
            ));
        }}
        statement_index = checked_add(statement_index, 1);
    }}

    var counters: Vec<i64> = vec_new<i64>(allocator, 3);
    vec_push<i64>(counters, vec_len<i64>(binding_starts));
    vec_push<i64>(counters, 0);
    vec_push<i64>(counters, 0);

    statement_index = 0;
    while (statement_index < vec_len<StatementRecord>(statements)) {{
        let statement: StatementRecord = vec_get<StatementRecord>(statements, statement_index);
        let kind: i32 = statement_record_kind(statement);
        if (kind == 20) {{
            let expression_index: i64 = probe_expression_operand(statement, operands);
            let expression: StatementOperand = vec_get<StatementOperand>(operands, expression_index);
            let source_local: i64 = probe_emit_expression(
                source, tokens, binding_starts, binding_lengths,
                statement_operand_start(expression), statement_operand_length(expression),
                allocator, output, counters
            );
            let binding_operand_index: i64 = probe_binding_operand(statement, operands);
            let binding_operand: StatementOperand = vec_get<StatementOperand>(operands, binding_operand_index);
            let binding_id: i64 = hir_find_binding_id(
                source, binding_starts, binding_lengths,
                statement_operand_start(binding_operand), statement_operand_length(binding_operand)
            );
            let statement_hir_id: i64 = vec_get<i64>(counters, 2);
            let instruction_id: i64 = vec_get<i64>(counters, 1);
            vec_push<MirFunctionRecord>(output, function_mir_copy(
                statement_record_start(statement), statement_record_length(statement), instruction_id,
                binding_id, source_local, binding_id, statement_hir_id
            ));
            vec_set<i64>(counters, 1, checked_add(instruction_id, 1));
            vec_set<i64>(counters, 2, checked_add(statement_hir_id, 1));
        }}
        if (kind == 21) {{
            let expression_index: i64 = probe_expression_operand(statement, operands);
            let expression: StatementOperand = vec_get<StatementOperand>(operands, expression_index);
            let source_local: i64 = probe_emit_expression(
                source, tokens, binding_starts, binding_lengths,
                statement_operand_start(expression), statement_operand_length(expression),
                allocator, output, counters
            );
            let binding_operand_index: i64 = probe_binding_operand(statement, operands);
            let binding_operand: StatementOperand = vec_get<StatementOperand>(operands, binding_operand_index);
            let binding_id: i64 = hir_find_binding_id(
                source, binding_starts, binding_lengths,
                statement_operand_start(binding_operand), statement_operand_length(binding_operand)
            );
            let statement_hir_id: i64 = vec_get<i64>(counters, 2);
            let instruction_id: i64 = vec_get<i64>(counters, 1);
            vec_push<MirFunctionRecord>(output, function_mir_copy(
                statement_record_start(statement), statement_record_length(statement), instruction_id,
                binding_id, source_local, binding_id, statement_hir_id
            ));
            vec_set<i64>(counters, 1, checked_add(instruction_id, 1));
            vec_set<i64>(counters, 2, checked_add(statement_hir_id, 1));
        }}
        if (kind == 22) {{
            let expression_index: i64 = probe_expression_operand(statement, operands);
            let expression: StatementOperand = vec_get<StatementOperand>(operands, expression_index);
            let result_local: i64 = probe_emit_expression(
                source, tokens, binding_starts, binding_lengths,
                statement_operand_start(expression), statement_operand_length(expression),
                allocator, output, counters
            );
            let statement_hir_id: i64 = vec_get<i64>(counters, 2);
            vec_push<MirFunctionRecord>(output, function_mir_return(
                statement_record_start(statement), statement_record_length(statement), result_local, statement_hir_id
            ));
            vec_set<i64>(counters, 2, checked_add(statement_hir_id, 1));
        }}
        statement_index = checked_add(statement_index, 1);
    }}

    print(validate_function_mir_records(output));
    print(vec_len<MirFunctionRecord>(output));
    var output_index: i64 = 0;
    while (output_index < vec_len<MirFunctionRecord>(output)) {{
        let node: MirFunctionRecord = vec_get<MirFunctionRecord>(output, output_index);
        print(function_mir_kind(node)); print(function_mir_start(node)); print(function_mir_length(node));
        print(function_mir_id(node)); print(function_mir_result(node)); print(function_mir_left(node));
        print(function_mir_right(node)); print(function_mir_symbol_start(node)); print(function_mir_symbol_length(node));
        print(function_mir_symbol_code(node)); print(function_mir_type_code(node)); print(function_mir_numeric_policy(node));
        print(function_mir_binding_id(node)); print(function_mir_mutable(node)); print(function_mir_hir_node_id(node));
        print(function_mir_ordinal(node));
        output_index = checked_add(output_index, 1);
    }}

    drop(counters); drop(binding_lengths); drop(binding_starts); drop(output);
    drop(operands); drop(statements); drop(tokens);
    return 0;
}}

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "{escaped}");
        emit_function(source, allocator);
        drop(source);
    }}
    return 0;
}}
'''


def _project_with_probe(tmp_path: Path):
    project_root = tmp_path / "bootstrap_mir_function_parity"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (project_root / "src/mir_function_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = project_root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8").replace(
        'entry = "src/lexer.mrt"', 'entry = "src/mir_function_probe.mrt"'
    )
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), project_root


def _parse_output(output: str):
    values = [int(value) for value in output.splitlines()]
    validation, count = values[:2]
    fields = values[2:]
    assert len(fields) == count * 16
    records = [tuple(fields[index:index + 16]) for index in range(0, len(fields), 16)]
    return validation, records


def _canonical(actual):
    validation, records = actual
    assert validation == 0
    native = lower_native_function_mir_records(records, SOURCE, module_name="demo")
    return canonical_mir_json(native)


def test_repository_straight_line_function_mir_has_real_interpreter_and_native_parity(tmp_path):
    project, project_root = _project_with_probe(tmp_path)
    expected = canonical_mir_json(_reference_mir())

    interpreted = _parse_output(interpret(project))
    assert _canonical(interpreted) == expected

    _, _, executable = build(project, project_root / "mir_function_parity")
    native = _parse_output(
        subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    )
    assert native == interpreted
    assert _canonical(native) == expected
