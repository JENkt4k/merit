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
TESTS = Path(__file__).parent


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


LEXER = _load_module("merit_bootstrap_span_lexer", TESTS / "test_bootstrap_lexer.py")
STATEMENTS = _load_module(
    "merit_bootstrap_span_statements", TESTS / "test_bootstrap_statement_operands.py"
)
CLAUSES = _load_module(
    "merit_bootstrap_span_clauses", TESTS / "test_bootstrap_clause_operands.py"
)
NATIVE_AST = _load_module(
    "merit_bootstrap_span_native_ast", TESTS / "test_bootstrap_native_ast.py"
)


def _adjust_expression_records(expression: str, offset: int):
    return [
        (kind, start + offset, length, left, right)
        for kind, start, length, left, right in LEXER.reference_expression(expression)
    ]


def _adjust_ast_records(expression: str, offset: int):
    adjusted = []
    for kind, start, length, left, right, group_start, group_length, group_parent in NATIVE_AST.reference_ast_records(expression):
        adjusted.append(
            (
                kind,
                start + offset,
                length,
                left,
                right,
                group_start + offset if group_start >= 0 else group_start,
                group_length,
                group_parent,
            )
        )
    return adjusted


def _expression_operands(source: str):
    _, statement_operands = STATEMENTS.reference_statement_records(source)
    _, clause_operands = CLAUSES.reference_clause_records(source)
    return [
        *( (1, index, operand) for index, operand in enumerate(statement_operands) if operand[0] == 3 ),
        *( (2, index, operand) for index, operand in enumerate(clause_operands) if operand[0] == 3 ),
    ]


def expected_span_payload(source: str):
    data = source.encode("utf-8")
    result = []
    for category, index, (_, start, length) in _expression_operands(source):
        expression = data[start : start + length].decode("utf-8")
        result.append(
            (
                category,
                index,
                start,
                length,
                0,
                _adjust_expression_records(expression, start),
                _adjust_ast_records(expression, start),
            )
        )
    return result


def _probe_loop(vector_type: str, operand_type: str, prefix: str, category: int) -> str:
    return f'''        var {prefix}_index: i64 = 0;
        while ({prefix}_index < vec_len<{operand_type}>({prefix}_operands)) {{
            let operand: {operand_type} = vec_get<{operand_type}>({prefix}_operands, {prefix}_index);
            if {prefix}_operand_kind(operand) == 3 {{
                let span_start: i64 = {prefix}_operand_start(operand);
                let span_length: i64 = {prefix}_operand_length(operand);
                let span_expressions: Vec<ExpressionNode> = parse_expression_span(source, tokens, span_start, span_length, allocator);
                let span_validation: i32 = validate_expression_ast_records(span_expressions);
                let span_ast: Vec<AstNodeRecord> = lower_expression_span_ast(source, tokens, span_start, span_length, allocator);
                print({category});
                print({prefix}_index);
                print(span_start);
                print(span_length);
                print(span_validation);
                print(vec_len<ExpressionNode>(span_expressions));
                var span_expression_index: i64 = 0;
                while (span_expression_index < vec_len<ExpressionNode>(span_expressions)) {{
                    let expression: ExpressionNode = vec_get<ExpressionNode>(span_expressions, span_expression_index);
                    print(expression_kind(expression));
                    print(expression_start(expression));
                    print(expression_length(expression));
                    print(expression_left(expression));
                    print(expression_right(expression));
                    span_expression_index = checked_add(span_expression_index, 1);
                }}
                print(vec_len<AstNodeRecord>(span_ast));
                var span_ast_index: i64 = 0;
                while (span_ast_index < vec_len<AstNodeRecord>(span_ast)) {{
                    let ast: AstNodeRecord = vec_get<AstNodeRecord>(span_ast, span_ast_index);
                    print(ast_kind(ast));
                    print(ast_start(ast));
                    print(ast_length(ast));
                    print(ast_left(ast));
                    print(ast_right(ast));
                    print(ast_group_start(ast));
                    print(ast_group_length(ast));
                    print(ast_group_parent(ast));
                    span_ast_index = checked_add(span_ast_index, 1);
                }}
                drop(span_ast);
                drop(span_expressions);
            }}
            {prefix}_index = checked_add({prefix}_index, 1);
        }}
'''


def _inject_probe(source: str) -> str:
    source = source.replace(
        "import bootstrap_syntax;\n",
        "import bootstrap_syntax;\n"
        "import bootstrap_statements;\n"
        "import bootstrap_clauses;\n"
        "import bootstrap_expression_spans;\n",
        1,
    )
    probe = (
        '''        let statement_operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);
        let clause_operands: Vec<ClauseOperand> = parse_clause_operands(source, tokens, allocator);
        print(-10);
'''
        + _probe_loop("Vec<StatementOperand>", "StatementOperand", "statement", 1)
        + _probe_loop("Vec<ClauseOperand>", "ClauseOperand", "clause", 2)
        + '''        print(-11);
        drop(clause_operands);
        drop(statement_operands);
'''
    )
    marker = "        drop(expressions);\n"
    assert marker in source
    return source.replace(marker, probe + marker, 1)


def _project_with_source(tmp_path, source_text: str):
    project_root = tmp_path / "bootstrap_expression_span_integration"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    source = lexer_path.read_text(encoding="utf-8")
    replacement = (
        "        let source: Buffer = buffer_from_string(allocator, "
        f"{json.dumps(source_text)});"
    )
    source, replacements = re.subn(
        r"^        let source: Buffer = buffer_from_string\(allocator, .+\);$",
        lambda _: replacement,
        source,
        count=1,
        flags=re.MULTILINE,
    )
    assert replacements == 1
    lexer_path.write_text(_inject_probe(source), encoding="utf-8")
    return load_project(project_root / "Merit.toml"), project_root


def _parse_probe(output: str):
    payload = output.rsplit("-10\n", 1)[1].split("-11\n", 1)[0]
    values = [int(value) for value in payload.splitlines()]
    cursor = 0
    result = []
    while cursor < len(values):
        category, index, start, length, validation = values[cursor : cursor + 5]
        cursor += 5
        expression_count = values[cursor]
        cursor += 1
        expression_fields = values[cursor : cursor + expression_count * 5]
        cursor += expression_count * 5
        expressions = [
            tuple(expression_fields[position : position + 5])
            for position in range(0, len(expression_fields), 5)
        ]
        ast_count = values[cursor]
        cursor += 1
        ast_fields = values[cursor : cursor + ast_count * 8]
        cursor += ast_count * 8
        ast = [
            tuple(ast_fields[position : position + 8])
            for position in range(0, len(ast_fields), 8)
        ]
        result.append((category, index, start, length, validation, expressions, ast))
    return result


CASES = [
    "module integrated\n"
    "fn compute(x:i64)->i64 effects [read] requires_caps [allocate] "
    "requires (x+1)*2 >= call(3,4); ensures Box { value: x+1 }.value > x; "
    "{ let y:i64=x+2*3; print(call(y,4)); if y>2 { return y; } return 0; }\n",
    "module boundaries\n"
    "fn main()->i32 requires value != limit; ensures wrap(1+2) == 3; "
    "{ if value != limit { return pair(1,2).field; } "
    "replace(value,Box { value: 1+2 }.value); return (1+2)*3; }\n",
]


@pytest.mark.parametrize(
    "source_text", CASES, ids=("statement-and-clause-expressions", "brace-boundaries")
)
def test_statement_and_clause_expression_spans_reuse_expression_ast_pipeline(
    tmp_path, source_text
):
    expected = expected_span_payload(source_text)
    assert expected
    project, project_root = _project_with_source(tmp_path, source_text)

    interpreted = _parse_probe(interpret(project))
    assert interpreted == expected

    _, _, executable = build(project, project_root / "bootstrap_expression_span")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native = _parse_probe(native_output)
    assert native == expected
    assert native == interpreted


def test_span_oracle_keeps_following_block_outside_condition_expression():
    source = (
        "module boundary\nfn main()->i32 { "
        "if value != limit { return 1; } return 0; }\n"
    )
    payload = expected_span_payload(source)
    condition = next(item for item in payload if item[0] == 1 and item[3] == len("value != limit"))
    assert condition[5][-1][0] == 41
    assert condition[5][-1][1:3] == (source.index("value != limit"), len("value != limit"))
    assert all(record[0] != 70 for record in condition[5])
