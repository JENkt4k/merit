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
        "merit_bootstrap_clause_reference", REFERENCE_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


REFERENCE = _load_reference_module()
CLAUSE_KINDS = {
    b"effects": 11,
    b"requires_caps": 12,
    b"requires": 13,
    b"ensures": 14,
}


def _text(data: bytes, token):
    _, start, length = token
    return data[start : start + length]


def _list_close(data: bytes, tokens, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(tokens)):
        text = _text(data, tokens[index])
        if text == b"[":
            depth += 1
        elif text == b"]":
            if depth == 1:
                return index
            if depth:
                depth -= 1
    return -1


def _expression_end(data: bytes, tokens, start_index: int) -> int:
    parens = brackets = braces = 0
    for index in range(start_index, len(tokens)):
        text = _text(data, tokens[index])
        if text == b";" and parens == brackets == braces == 0:
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


def _span(tokens, first: int, last_exclusive: int):
    if first < 0 or last_exclusive <= first:
        return None
    _, start, _ = tokens[first]
    _, last_start, last_length = tokens[last_exclusive - 1]
    return start, last_start + last_length - start


def _clause_operands(data: bytes, tokens, index: int, kind: int):
    if kind in (11, 12):
        open_index = index + 1
        if open_index >= len(tokens) or _text(data, tokens[open_index]) != b"[":
            return []
        close_index = _list_close(data, tokens, open_index)
        if close_index < 0:
            return []
        operand_kind = 1 if kind == 11 else 2
        return [
            (operand_kind, token[1], token[2])
            for token in tokens[open_index + 1 : close_index]
            if token[0] == 1
        ]

    first = index + 1
    semicolon = _expression_end(data, tokens, first)
    span = _span(tokens, first, semicolon)
    return [(3, *span)] if span else []


def _clause_end(data: bytes, tokens, index: int, kind: int) -> int:
    if kind in (11, 12):
        open_index = index + 1
        if open_index < len(tokens) and _text(data, tokens[open_index]) == b"[":
            close_index = _list_close(data, tokens, open_index)
            if close_index >= 0:
                _, start, length = tokens[close_index]
                return start + length
        return len(data)

    semicolon = _expression_end(data, tokens, index + 1)
    if semicolon >= 0:
        _, start, length = tokens[semicolon]
        return start + length
    return len(data)


def reference_clause_records(source: str):
    data = source.encode("utf-8")
    tokens = REFERENCE.reference_tokens(source)
    records = []
    operands = []
    depth = 0

    for index, token in enumerate(tokens):
        text = _text(data, token)
        if text == b"}" and depth:
            depth -= 1

        if depth == 0:
            kind = CLAUSE_KINDS.get(text, 0)
            if kind:
                clause_operands = _clause_operands(data, tokens, index, kind)
                start = token[1]
                end = _clause_end(data, tokens, index, kind)
                records.append(
                    (kind, start, end - start, len(operands), len(clause_operands))
                )
                operands.extend(clause_operands)

        if text == b"{":
            depth += 1

    return records, operands


def _inject_probe(source: str) -> str:
    source = source.replace(
        "import bootstrap_syntax;\n",
        "import bootstrap_syntax;\nimport bootstrap_clauses;\n",
        1,
    )
    probe = '''        let clause_records: Vec<ClauseRecord> = parse_clause_records(source, tokens, allocator);
        let clause_operands: Vec<ClauseOperand> = parse_clause_operands(source, tokens, allocator);
        print(-8);
        print(vec_len<ClauseRecord>(clause_records));
        var clause_index: i64 = 0;
        while (clause_index < vec_len<ClauseRecord>(clause_records)) {
            let clause: ClauseRecord = vec_get<ClauseRecord>(clause_records, clause_index);
            print(clause_record_kind(clause));
            print(clause_record_start(clause));
            print(clause_record_length(clause));
            print(clause_record_first_operand(clause));
            print(clause_record_operand_count(clause));
            clause_index = checked_add(clause_index, 1);
        }
        print(-9);
        print(vec_len<ClauseOperand>(clause_operands));
        var clause_operand_index: i64 = 0;
        while (clause_operand_index < vec_len<ClauseOperand>(clause_operands)) {
            let operand: ClauseOperand = vec_get<ClauseOperand>(clause_operands, clause_operand_index);
            print(clause_operand_kind(operand));
            print(clause_operand_start(operand));
            print(clause_operand_length(operand));
            clause_operand_index = checked_add(clause_operand_index, 1);
        }
        drop(clause_operands);
        drop(clause_records);
'''
    marker = "        drop(expressions);\n"
    assert marker in source
    return source.replace(marker, probe + marker, 1)


def _project_with_source(tmp_path, source_text: str):
    project_root = tmp_path / "bootstrap_clause_operands"
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
    payload = output.rsplit("-8\n", 1)[1]
    records_payload, operands_payload = payload.split("-9\n", 1)

    record_values = [int(value) for value in records_payload.splitlines()]
    record_count = record_values[0]
    record_fields = record_values[1:]
    assert len(record_fields) == record_count * 5
    records = [
        tuple(record_fields[index : index + 5])
        for index in range(0, len(record_fields), 5)
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
    "module clauses\n"
    "fn compute(x:i64)->i64 "
    "effects [read, write, deterministic] "
    "requires_caps [filesystem_read, allocate] "
    "requires check(x,pair(1,2)) == 1; "
    "ensures Result { value: x + 1 }.value >= x; "
    "{ print(requires); return x; }\n",
    "module multiple\n"
    "fn first()->i32 effects [] requires_caps [] "
    "requires (1+2)*3 == 9; ensures wrap(call(1,2)) > 0; "
    "{ return 1; } "
    "fn second()->i32 effects [pure] requires_caps [audit] "
    "requires Box { value: f(1,2) }.value > 0; "
    "ensures 2 > 1; { return 2; }\n",
]


@pytest.mark.parametrize("source_text", CASES, ids=("all-clause-operands", "multiple-functions"))
def test_typed_clause_records_match_independent_oracle_interpreter_and_native(
    tmp_path, source_text
):
    expected = reference_clause_records(source_text)
    project, project_root = _project_with_source(tmp_path, source_text)

    interpreted = _parse_probe(interpret(project))
    assert interpreted == expected

    _, _, executable = build(project, project_root / "bootstrap_clause_operands")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert _parse_probe(native) == expected
    assert _parse_probe(native) == interpreted


def test_clause_record_operand_ranges_are_contiguous():
    records, operands = reference_clause_records(CASES[0])
    cursor = 0
    for record in records:
        assert record[3] == cursor
        cursor += record[4]
    assert cursor == len(operands)


def test_clause_oracle_ignores_clause_like_identifiers_inside_function_body():
    records, operands = reference_clause_records(
        "module depth\n"
        "fn f()->i32 effects [pure] requires 1==1; "
        "{ print(requires); print(ensures); print(effects); return 0; }\n"
    )
    assert [record[0] for record in records] == [11, 13]
    assert len(operands) == 2
