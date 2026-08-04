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
DEFAULT_SOURCE = 'module demo\nfn main()->i32 { print("ok"); return 0; }\n'


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
    syntax = reference_syntax(source, tokens)
    diagnostics = reference_diagnostics(source, tokens)
    values = [len(tokens), *(value for token in tokens for value in token), -1, len(syntax), *(value for node in syntax for value in node), -2, len(diagnostics), *(value for diagnostic in diagnostics for value in diagnostic)]
    return "".join(f"{value}\n" for value in values)


def reference_syntax(source, tokens):
    data = source.encode("utf-8")
    kinds = {b"module": 1, b"fn": 2, b"struct": 3, b"enum": 4, b"capability": 5, b"decimal": 6, b"bounded": 7, b"trait": 8, b"impl": 9, b"destructor": 10, b"effects": 11, b"requires_caps": 12, b"requires": 13, b"ensures": 14}
    statements = {b"let": 20, b"var": 21, b"return": 22, b"print": 23, b"drop": 24, b"if": 25, b"while": 26, b"match": 27, b"with": 28, b"replace": 29}
    nodes = []
    depth = 0
    for index, (token_kind, start, length) in enumerate(tokens):
        text = data[start:start + length]
        if token_kind == 4 and text == b"}" and depth > 0:
            depth -= 1
        syntax_kind = kinds.get(text, 0) if depth == 0 else statements.get(text, 0)
        if syntax_kind:
            end = start + length
            if syntax_kind <= 10 and index + 1 < len(tokens) and tokens[index + 1][0] == 1:
                _, name_start, name_length = tokens[index + 1]
                end = name_start + name_length
            nodes.append((syntax_kind, start, end - start))
        if token_kind == 4 and text == b"{":
            depth += 1
    return nodes


def reference_diagnostics(source, tokens):
    data = source.encode("utf-8")
    keywords = {b"module", b"fn", b"struct", b"enum", b"capability", b"decimal", b"bounded", b"trait", b"impl", b"destructor"}
    diagnostics = []
    depth = 0
    for index, (kind, start, length) in enumerate(tokens):
        text = data[start:start + length]
        if kind == 5:
            diagnostics.append((4, start, length))
        if kind == 4 and text == b"}":
            if depth == 0:
                diagnostics.append((2, start, length))
            else:
                depth -= 1
        if depth == 0 and text in keywords:
            if index + 1 >= len(tokens) or tokens[index + 1][0] != 1:
                diagnostics.append((1, start, length))
        if kind == 4 and text == b"{":
            depth += 1
    if depth > 0:
        diagnostics.append((3, len(data), 0))
    return diagnostics


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
    assert "merit_Vec__SyntaxNode _merit_result = {0};" in generated
    lexer_body = generated[generated.rindex("merit_Vec__Token merit_lex("):generated.index("int32_t main(")]
    assert lexer_body.index("merit_buffer_get(_merit_expr_") < lexer_body.index("merit_vec_push__Token(")
    operations = {(site["operation"], site["capability"]) for site in checker.hazardous_operations}
    assert ("vec_new__Token", "allocate") in operations
    assert ("vec_push__Token", "allocate") in operations
    assert ("vec_new__SyntaxNode", "allocate") in operations
    assert ("vec_push__SyntaxNode", "allocate") in operations


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
        'module all\ncapability io; decimal Money(8,2,half_even); bounded Count(i32,0,9); struct S { value:i32; } enum E { A } trait T { fn run()->i32; } impl T for S { fn run()->i32 { return 1; } } destructor S { return 0; } fn main()->i32 { return 0; }',
        'module { } } struct Open {',
        'module contracts\nfn checked(value:i32)->i32 effects [read] requires_caps [io] requires value >= 0; ensures result >= value; { return value; }',
        'module statements\nfn all()->i32 { let x:i32=0; var y:i32=1; print(x); drop(y); if x { replace(x,1); } while y { return 0; } match(x) { A => { return 1; } } with capability io { print(y); } return 2; }',
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


def test_bootstrap_parser_allocation_is_compile_fail_without_capability_contract():
    project = load_project(MANIFEST)
    parser = next(function for function in project.program.functions if function.name == "parse_top_level")
    parser.requires_caps = []
    with pytest.raises(CompileError, match="vec_new__SyntaxNode requires capabilities"):
        check(project)


def test_bootstrap_diagnostics_allocation_is_compile_fail_without_capability_contract():
    project = load_project(MANIFEST)
    diagnostics = next(function for function in project.program.functions if function.name == "parse_diagnostics")
    diagnostics.requires_caps = []
    with pytest.raises(CompileError, match="vec_new__ParseDiagnostic requires capabilities"):
        check(project)
