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
DEFAULT_EXPRESSION = "1 + 2 * 3 == 7"


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


def expected_output(source, expression=DEFAULT_EXPRESSION):
    tokens = reference_tokens(source)
    syntax = reference_syntax(source, tokens)
    diagnostics = reference_diagnostics(source, tokens)
    expressions = reference_expression(expression)
    values = [len(tokens), *(value for token in tokens for value in token), -1, len(syntax), *(value for node in syntax for value in node), -2, len(diagnostics), *(value for diagnostic in diagnostics for value in diagnostic), -3, len(expressions), *(value for node in expressions for value in node)]
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
            elif syntax_kind >= 20:
                end = statement_end(data, tokens, index, syntax_kind)
            nodes.append((syntax_kind, start, end - start))
        if token_kind == 4 and text == b"{":
            depth += 1
    return nodes


def statement_end(data, tokens, start_index, kind):
    for token_kind, start, length in tokens[start_index + 1:]:
        text = data[start:start + length]
        if token_kind == 4 and 25 <= kind <= 28 and text == b"{":
            return start + length
        if token_kind == 4 and text == b";":
            return start + length
    return len(data)


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


def reference_expression(source):
    data = source.encode("utf-8")
    tokens = reference_tokens(source)
    nodes = []
    cursor = 0
    operators = {b"==": 40, b"!=": 41, b">=": 42, b"<=": 43, b">": 44, b"<": 45, b"+": 50, b"-": 51, b"*": 60, b"/": 61}

    def push(kind, start, length, left=-1, right=-1):
        nodes.append((kind, start, length, left, right))
        return len(nodes) - 1

    def primary():
        nonlocal cursor
        if cursor >= len(tokens):
            return push(39, len(data), 0)
        token_kind, start, length = tokens[cursor]
        text = data[start:start + length]
        if text == b"(":
            cursor += 1
            child = comparison()
            end = start + length
            if cursor < len(tokens):
                _, closing_start, closing_length = tokens[cursor]
                if data[closing_start:closing_start + closing_length] == b")":
                    end = closing_start + closing_length
                    cursor += 1
            return postfix(push(33, start, end - start, child))
        cursor += 1
        kind = {1: 30, 2: 31, 3: 32}.get(token_kind, 39)
        return postfix(push(kind, start, length))

    def postfix(left):
        nonlocal cursor
        while cursor < len(tokens):
            _, start, length = tokens[cursor]
            text = data[start:start + length]
            if text == b"(":
                cursor += 1
                arguments = -1
                if cursor < len(tokens):
                    _, possible_start, possible_length = tokens[cursor]
                    possible = data[possible_start:possible_start + possible_length]
                else:
                    possible = b""
                if possible != b")":
                    arguments = comparison()
                    while cursor < len(tokens):
                        _, comma_start, comma_length = tokens[cursor]
                        if data[comma_start:comma_start + comma_length] != b",":
                            break
                        cursor += 1
                        next_argument = comparison()
                        argument_start = nodes[arguments][1]
                        argument_end = nodes[next_argument][1] + nodes[next_argument][2]
                        arguments = push(37, argument_start, argument_end - argument_start, arguments, next_argument)
                end = start + length
                if cursor < len(tokens):
                    _, closing_start, closing_length = tokens[cursor]
                    if data[closing_start:closing_start + closing_length] == b")":
                        end = closing_start + closing_length
                        cursor += 1
                call_start = nodes[left][1]
                left = push(34, call_start, end - call_start, left, arguments)
            elif text == b"<" and cursor + 3 < len(tokens):
                type_kind, type_start, type_length = tokens[cursor + 1]
                _, close_start, close_length = tokens[cursor + 2]
                _, call_start, call_length = tokens[cursor + 3]
                if type_kind == 1 and data[close_start:close_start + close_length] == b">" and data[call_start:call_start + call_length] == b"(":
                    type_index = push(30, type_start, type_length)
                    generic_start = nodes[left][1]
                    left = push(36, generic_start, close_start + close_length - generic_start, left, type_index)
                    cursor += 3
                else:
                    break
            elif text == b"{":
                cursor += 1
                initializers = -1
                while cursor < len(tokens):
                    _, possible_start, possible_length = tokens[cursor]
                    if data[possible_start:possible_start + possible_length] == b"}":
                        break
                    field_index = push(30, possible_start, possible_length)
                    cursor += 2
                    value_index = comparison()
                    initializer_end = nodes[value_index][1] + nodes[value_index][2]
                    initializer_index = push(38, possible_start, initializer_end - possible_start, field_index, value_index)
                    if initializers == -1:
                        initializers = initializer_index
                    else:
                        initializer_start = nodes[initializers][1]
                        initializers = push(37, initializer_start, initializer_end - initializer_start, initializers, initializer_index)
                    if cursor < len(tokens):
                        _, separator_start, separator_length = tokens[cursor]
                        if data[separator_start:separator_start + separator_length] == b",":
                            cursor += 1
                        else:
                            break
                end = start + length
                if cursor < len(tokens):
                    _, closing_start, closing_length = tokens[cursor]
                    if data[closing_start:closing_start + closing_length] == b"}":
                        end = closing_start + closing_length
                        cursor += 1
                constructor_start = nodes[left][1]
                left = push(70, constructor_start, end - constructor_start, left, initializers)
            elif text == b".":
                cursor += 1
                field_index = -1
                end = start + length
                if cursor < len(tokens) and tokens[cursor][0] == 1:
                    _, field_start, field_length = tokens[cursor]
                    field_index = push(30, field_start, field_length)
                    end = field_start + field_length
                    cursor += 1
                receiver_start = nodes[left][1]
                left = push(35, receiver_start, end - receiver_start, left, field_index)
            else:
                break
        return left

    def combine(kind, left, right):
        start = nodes[left][1]
        end = nodes[right][1] + nodes[right][2]
        return push(kind, start, end - start, left, right)

    def product():
        nonlocal cursor
        left = primary()
        while cursor < len(tokens):
            _, start, length = tokens[cursor]
            kind = operators.get(data[start:start + length], 0)
            if kind not in (60, 61):
                break
            cursor += 1
            left = combine(kind, left, primary())
        return left

    def total():
        nonlocal cursor
        left = product()
        while cursor < len(tokens):
            _, start, length = tokens[cursor]
            kind = operators.get(data[start:start + length], 0)
            if kind not in (50, 51):
                break
            cursor += 1
            left = combine(kind, left, product())
        return left

    def comparison():
        nonlocal cursor
        left = total()
        if cursor < len(tokens):
            _, start, length = tokens[cursor]
            kind = operators.get(data[start:start + length], 0)
            if 40 <= kind <= 45:
                cursor += 1
                return combine(kind, left, total())
        return left

    comparison()
    return nodes


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
    assert "merit_Vec__ExpressionNode _merit_result = {0};" in generated
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


def project_with_expression(tmp_path, expression_text):
    project_root = tmp_path / "bootstrap_expression"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    source = lexer_path.read_text()
    replacement = f"        let expression_source: Buffer = buffer_from_string(allocator, {json.dumps(expression_text)});"
    source, replacements = re.subn(r"^        let expression_source: Buffer = buffer_from_string\(allocator, .+\);$", lambda _: replacement, source, count=1, flags=re.MULTILINE)
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
        'module incomplete\nfn value()->i32 { return 1',
    ],
)
def test_bootstrap_lexer_matches_independent_reference_corpus(tmp_path, source_text):
    project, project_root = project_with_source(tmp_path, source_text)
    expected = expected_output(source_text)
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "bootstrap_lexer")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == expected


@pytest.mark.parametrize("expression", ["1+2*3", "(1+2)*3", "a-b-c", "a==b+1", '"value"', "a/2+4", "f()", "f(1,2+3)", "account.balance+1", "f(g(1)).value", "Point { x:1, y:2+3 }.x", "identity<i64>(1)"])
def test_bootstrap_expression_precedence_matches_independent_reference(tmp_path, expression):
    project, project_root = project_with_expression(tmp_path, expression)
    expected = expected_output(DEFAULT_SOURCE, expression)
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "bootstrap_expression")
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


def test_bootstrap_expression_allocation_is_compile_fail_without_capability_contract():
    project = load_project(MANIFEST)
    expression_parser = next(function for function in project.program.functions if function.name == "parse_expression_tokens")
    expression_parser.requires_caps = []
    with pytest.raises(CompileError, match="vec_new__ExpressionNode requires capabilities"):
        check(project)
