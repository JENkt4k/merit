import shutil
import subprocess
import json
import re
from pathlib import Path

import pytest

from merit.compiler import CompileError
from merit.project.build import build, check, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
MANIFEST = PROJECT / "Merit.toml"
DEFAULT_SOURCE = 'let total: i64 = 42;\nprint("ok", total + 1); // ok\n'


def reference_tokens(source):
    data = source.encode("utf-8")
    tokens = []
    cursor = 0
    pairs = {b"->", b"=>", b"==", b"!=", b">=", b"<=", b"::"}
    while cursor < len(data):
        byte = data[cursor]
        if byte in (32, 9, 10, 13):
            cursor += 1
            continue
        if data[cursor:cursor + 2] == b"//":
            cursor += 2
            while cursor < len(data) and data[cursor] != 10:
                cursor += 1
            continue
        start = cursor
        if byte == 95 or 65 <= byte <= 90 or 97 <= byte <= 122:
            cursor += 1
            while cursor < len(data) and (data[cursor] == 95 or 48 <= data[cursor] <= 57 or 65 <= data[cursor] <= 90 or 97 <= data[cursor] <= 122):
                cursor += 1
            kind = 1
        elif 48 <= byte <= 57:
            cursor += 1
            while cursor < len(data) and 48 <= data[cursor] <= 57:
                cursor += 1
            if cursor < len(data) and data[cursor] == 46:
                cursor += 1
                while cursor < len(data) and 48 <= data[cursor] <= 57:
                    cursor += 1
            if cursor < len(data) and data[cursor] in (69, 101):
                cursor += 1
                if cursor < len(data) and data[cursor] in (43, 45):
                    cursor += 1
                while cursor < len(data) and 48 <= data[cursor] <= 57:
                    cursor += 1
            kind = 2
        elif byte == 34:
            cursor += 1
            closed = False
            while cursor < len(data):
                if data[cursor] == 34:
                    cursor += 1
                    closed = True
                    break
                if data[cursor] == 92 and cursor + 1 < len(data):
                    cursor += 2
                else:
                    cursor += 1
            kind = 3 if closed else 5
        else:
            cursor += 2 if data[cursor:cursor + 2] in pairs else 1
            kind = 4
        tokens.append((kind, start, cursor - start))
    return tokens


def expected_output(source):
    tokens = reference_tokens(source)
    values = [len(tokens), *(value for token in tokens for value in token)]
    return "".join(f"{value}\n" for value in values)


EXPECTED = expected_output(DEFAULT_SOURCE)


def test_bootstrap_lexer_matches_interpreter_native_and_ordered_c(tmp_path):
    project = load_project(MANIFEST)
    checker = check(project)
    assert interpret(project) == EXPECTED
    c_path, _, executable = build(project, tmp_path / "bootstrap_lexer")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == EXPECTED
    generated = c_path.read_text()
    assert "merit_Vec__Token _merit_result = {0};" in generated
    lexer_body = generated[generated.rindex("merit_Vec__Token merit_lex("):generated.index("int32_t main(")]
    assert lexer_body.index("merit_buffer_get(_merit_expr_") < lexer_body.index("merit_vec_push__Token(")
    operations = {(site["operation"], site["capability"]) for site in checker.hazardous_operations}
    assert ("vec_new__Token", "allocate") in operations
    assert ("vec_push__Token", "allocate") in operations


def project_with_source(tmp_path, source_text):
    project_root = tmp_path / "bootstrap_lexer"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    source = lexer_path.read_text()
    replacement = f"        let source: Buffer = buffer_from_string(allocator, {json.dumps(source_text)});"
    source, replacements = re.subn(r"^        let source: Buffer = buffer_from_string\(allocator, .+\);$", lambda _: replacement, source, count=1, flags=re.MULTILINE)
    assert replacements == 1
    lexer_path.write_text(source)
    return load_project(project_root / "Merit.toml"), project_root


@pytest.mark.parametrize(
    "source_text",
    [
        '"unterminated',
        "alpha_1 007\r\n// ignored\nbeta",
        'fn value()->i32 { if value>=1 { return value::next; } }',
        'left=>right == other != final <= upper',
        '"escaped \\\" quote" @',
        '0.00 12.5 1e6 2.5e-3',
    ],
)
def test_bootstrap_lexer_matches_independent_reference_corpus(tmp_path, source_text):
    project, project_root = project_with_source(tmp_path, source_text)
    expected = expected_output(source_text)
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "bootstrap_lexer")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == expected


def test_bootstrap_lexer_allocation_is_compile_fail_without_capability_contract():
    project = load_project(MANIFEST)
    lexer = next(function for function in project.program.functions if function.name == "lex")
    lexer.requires_caps = []
    with pytest.raises(CompileError, match="vec_new__Token requires capabilities"):
        check(project)
