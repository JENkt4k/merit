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


def _load_reference_module():
    specification = importlib.util.spec_from_file_location(
        "merit_bootstrap_statement_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()
STATEMENT_KINDS = {
    b"let": 20,
    b"var": 21,
    b"return": 22,
    b"print": 23,
    b"drop": 24,
    b"if": 25,
    b"while": 26,
    b"match": 27,
    b"with": 28,
    b"replace": 29,
}


def _text(data: bytes, token):
    _, start, length = token
    return data[start : start + length]


def _find_top_level(data: bytes, tokens, start_index: int, target: bytes) -> int:
    parens = brackets = braces = 0
    for index in range(start_index, len(tokens)):
        text = _text(data, tokens[index])
        if text == target and parens == brackets == braces == 0:
            return index
        if text == b"(":
            parens += 1
        elif text == b")" and parens:
            parens -= 1
        elif text == b"[":
            brackets += 1
        elif text == b"]" and brackets:
            brackets -= 1
        elif text == b"{":
            braces += 1
        elif text == b"}" and braces:
            braces -= 1
    return -1


def _statement_end(data: bytes, tokens, start_index: int, kind: int) -> int:
    parens = brackets = 0
    for token in tokens[start_index + 1 :]:
        text = _text(data, token)
        if text == b"(":
            parens += 1
        elif text == b")" and parens:
            parens -= 1
        elif text == b"[":
            brackets += 1
        elif text == b"]" and brackets:
            brackets -= 1
        if parens == brackets == 0:
            if 25 <= kind <= 28 and text == b"{":
                return token[1] + token[2]
            if text == b";":
                return token[1] + token[2]
    return len(data)


def _span(tokens, first: int, last_exclusive: int):
    if first < 0 or last_exclusive <= first:
        return None
    _, start, _ = tokens[first]
    _, last_start, last_length = tokens[last_exclusive - 1]
    return start, last_start + last_length - start


def _statement_operands(data: bytes, tokens, index: int, kind: int):
    result = []
    if kind in (20, 21):
        name_index = index + 1
        if name_index < len(tokens) and tokens[name_index][0] == 1:
            result.append((1, tokens[name_index][1], tokens[name_index][2]))
        colon_index = index + 2
        type_index = index + 3
        if (
            type_index < len(tokens)
            and _text(data, tokens[colon_index]) == b":"
            and tokens[type_index][0] == 1
        ):
            result.append((2, tokens[type_index][1], tokens[type_index][2]))
        equals = _find_top_level(data, tokens, index + 1, b"=")
        if equals >= 0:
            semicolon = _find_top_level(data, tokens, equals + 1, b";")
            span = _span(tokens, equals + 1, semicolon)
            if span:
                result.append((3, *span))
        return result
    if kind == 28:
        cap_index = index + 2
        if cap_index < len(tokens) and tokens[cap_index][0] == 1:
            result.append((4, tokens[cap_index][1], tokens[cap_index][2]))
        return result
    if kind == 29:
        open_index = index + 1
        if open_index >= len(tokens) or _text(data, tokens[open_index]) != b"(":
            return result
        first = open_index + 1
        comma = _find_top_level(data, tokens, first, b",")
        if comma < 0:
            return result
        span = _span(tokens, first, comma)
        if span:
            result.append((3, *span))
        second = comma + 1
        close = _find_top_level(data, tokens, second, b")")
        span = _span(tokens, second, close)
        if span:
            result.append((3, *span))
        return result
    first = index + 1
    delimiter = b"{" if 25 <= kind <= 27 else b";"
    end_index = _find_top_level(data, tokens, first, delimiter)
    span = _span(tokens, first, end_index)
    if span:
        result.append((3, *span))
    return result


def reference_statement_records(source: str):
    data = source.encode("utf-8")
    tokens = REFERENCE.reference_tokens(source)
    records = []
    operands = []
    depth = 0
    for index, token in enumerate(tokens):
        text = _text(data, token)
        if text == b"}" and depth:
            depth -= 1
        if depth:
            kind = STATEMENT_KINDS.get(text, 0)
            if kind:
                statement_operands = _statement_operands(data, tokens, index, kind)
                start = token[1]
                end = _statement_end(data, tokens, index, kind)
                records.append((kind, start, end - start, len(operands), len(statement_operands)))
                operands.extend(statement_operands)
        if text == b"{":
            depth += 1
    return records, operands


def _inject_probe(source: str) -> str:
    source = source.replace(
        "import bootstrap_syntax;\n",
        "import bootstrap_syntax;\nimport bootstrap_statements;\n",
        1,
    )
    probe = '''        let statement_records: Vec<StatementRecord> = parse_statement_records(source, tokens, allocator);
        let statement_operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);
        print(-6);
        print(vec_len<StatementRecord>(statement_records));
        var statement_index: i64 = 0;
        while (statement_index < vec_len<StatementRecord>(statement_records)) {
            let statement: StatementRecord = vec_get<StatementRecord>(statement_records, statement_index);
            print(statement_record_kind(statement));
            print(statement_record_start(statement));
            print(statement_record_length(statement));
            print(statement_record_first_operand(statement));
            print(statement_record_operand_count(statement));
            statement_index = checked_add(statement_index, 1);
        }
        print(-7);
        print(vec_len<StatementOperand>(statement_operands));
        var operand_index: i64 = 0;
        while (operand_index < vec_len<StatementOperand>(statement_operands)) {
            let operand: StatementOperand = vec_get<StatementOperand>(statement_operands, operand_index);
            print(statement_operand_kind(operand));
            print(statement_operand_start(operand));
            print(statement_operand_length(operand));
            operand_index = checked_add(operand_index, 1);
        }
        drop(statement_operands);
        drop(statement_records);
'''
    marker = "        drop(expressions);\n"
    assert marker in source
    return source.replace(marker, probe + marker, 1)


def _project_with_source(tmp_path, source_text: str):
    project_root = tmp_path / "bootstrap_statement_operands"
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
    payload = output.rsplit("-6\n", 1)[1]
    statements_payload, operands_payload = payload.split("-7\n", 1)
    statement_values = [int(value) for value in statements_payload.splitlines()]
    statement_count = statement_values[0]
    statement_fields = statement_values[1:]
    assert len(statement_fields) == statement_count * 5
    records = [
        tuple(statement_fields[index : index + 5])
        for index in range(0, len(statement_fields), 5)
    ]
    operand_values = [int(value) for value in operands_payload.splitlines()]
    operand_count = operand_values[0]
    operand_fields = operand_values[1:]
    assert len(operand_fields) == operand_count * 3
    operands = [
        tuple(operand_fields[index : index + 3])
        for index in range(0, len(operand_fields), 3)
    ]
    return records, operands


CASES = [
    "module statements\n"
    "fn main()->i32 { "
    "let x:i32=1+2*3; var y:i64=x; print(x+1); drop(y); "
    "if x>=1 { replace(x,x+2); } "
    "while x<3 { return x; } "
    "match(x) { A => { return 1; } } "
    "with capability io { print(y); } return 0; }\n",
    "module nested\n"
    "fn main()->i32 { "
    "let target:i32=f(1,2+3); "
    "replace(target[index(1,2)],f(3,4+5)); "
    "if check(f(1,2),3) { return g(4,5); } }\n",
]


@pytest.mark.parametrize("source_text", CASES, ids=("all-statement-operands", "nested-delimiters"))
def test_typed_statement_records_match_independent_oracle_interpreter_and_native(
    tmp_path, source_text
):
    expected = reference_statement_records(source_text)
    project, project_root = _project_with_source(tmp_path, source_text)

    interpreted = _parse_probe(interpret(project))
    assert interpreted == expected

    _, _, executable = build(project, project_root / "bootstrap_statement_operands")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert _parse_probe(native) == expected
    assert _parse_probe(native) == interpreted


def test_statement_record_operand_ranges_are_contiguous():
    records, operands = reference_statement_records(CASES[0])
    cursor = 0
    for record in records:
        assert record[3] == cursor
        cursor += record[4]
    assert cursor == len(operands)
