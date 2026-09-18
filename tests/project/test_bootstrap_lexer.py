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

TOKEN_REPRESENTATION = (
    ("token_identifier_kind", 1),
    ("token_number_kind", 2),
    ("token_string_kind", 3),
    ("token_punctuation_kind", 4),
    ("token_invalid_string_kind", 5),
    ("token_horizontal_tab_byte", 9),
    ("token_line_feed_byte", 10),
    ("token_carriage_return_byte", 13),
    ("token_space_byte", 32),
    ("token_exclamation_byte", 33),
    ("token_quote_byte", 34),
    ("token_open_paren_byte", 40),
    ("token_close_paren_byte", 41),
    ("token_asterisk_byte", 42),
    ("token_plus_byte", 43),
    ("token_comma_byte", 44),
    ("token_minus_byte", 45),
    ("token_dot_byte", 46),
    ("token_slash_byte", 47),
    ("token_digit_zero_byte", 48),
    ("token_digit_nine_byte", 57),
    ("token_colon_byte", 58),
    ("token_semicolon_byte", 59),
    ("token_less_than_byte", 60),
    ("token_equals_byte", 61),
    ("token_greater_than_byte", 62),
    ("token_uppercase_a_byte", 65),
    ("token_uppercase_e_byte", 69),
    ("token_uppercase_z_byte", 90),
    ("token_backslash_byte", 92),
    ("token_underscore_byte", 95),
    ("token_lowercase_a_byte", 97),
    ("token_lowercase_e_byte", 101),
    ("token_lowercase_z_byte", 122),
    ("token_open_brace_byte", 123),
    ("token_close_brace_byte", 125),
)


def token_representation_project(tmp_path):
    project_root = tmp_path / "bootstrap_token_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{",
        "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(),
        count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(f"print({name}());" for name, _ in TOKEN_REPRESENTATION)
    (project_root / "src/token_representation_probe.mrt").write_text(
        "module token_representation_probe\n"
        "import bootstrap_tokens;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_source = manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/token_representation_probe.mrt"',
    )
    manifest_path.write_text(manifest_source)
    return load_project(manifest_path), project_root


def test_bootstrap_token_and_character_representation_is_stable(tmp_path):
    project, project_root = token_representation_project(tmp_path)
    expected = "".join(f"{value}\n" for _, value in TOKEN_REPRESENTATION)
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


AST_HIR_REPRESENTATION = (
    ("syntax_module_kind", 1), ("syntax_function_kind", 2),
    ("syntax_struct_kind", 3), ("syntax_enum_kind", 4),
    ("syntax_capability_kind", 5), ("syntax_decimal_kind", 6),
    ("syntax_bounded_kind", 7), ("syntax_trait_kind", 8),
    ("syntax_impl_kind", 9), ("syntax_destructor_kind", 10),
    ("syntax_effects_clause_kind", 11),
    ("syntax_requires_caps_clause_kind", 12),
    ("syntax_requires_clause_kind", 13), ("syntax_ensures_clause_kind", 14),
    ("syntax_let_statement_kind", 20), ("syntax_var_statement_kind", 21),
    ("syntax_return_statement_kind", 22), ("syntax_print_statement_kind", 23),
    ("syntax_drop_statement_kind", 24), ("syntax_if_statement_kind", 25),
    ("syntax_while_statement_kind", 26), ("syntax_match_statement_kind", 27),
    ("syntax_with_statement_kind", 28), ("syntax_replace_statement_kind", 29),
    ("ast_identifier_kind", 30), ("ast_exact_numeric_kind", 31),
    ("ast_string_literal_kind", 32), ("ast_group_kind", 33),
    ("ast_call_kind", 34), ("ast_field_kind", 35),
    ("ast_generic_apply_kind", 36), ("ast_sequence_kind", 37),
    ("ast_field_initializer_kind", 38), ("ast_invalid_kind", 39),
    ("ast_equal_kind", 40), ("ast_not_equal_kind", 41),
    ("ast_greater_equal_kind", 42), ("ast_less_equal_kind", 43),
    ("ast_greater_kind", 44), ("ast_less_kind", 45),
    ("ast_add_kind", 50), ("ast_subtract_kind", 51),
    ("ast_multiply_kind", 60), ("ast_divide_kind", 61),
    ("ast_constructor_kind", 70),
    ("hir_invalid_kind", 0), ("hir_literal_kind", 1),
    ("hir_arithmetic_kind", 2),
    ("hir_group_alias_kind", 3), ("hir_identifier_kind", 4),
    ("hir_comparison_kind", 5), ("hir_call_kind", 6),
    ("hir_field_kind", 7), ("hir_argument_sequence_kind", 8),
    ("hir_symbol_reference_kind", 9), ("hir_constructor_kind", 10),
    ("hir_field_initializer_kind", 11), ("hir_string_literal_kind", 12),
    ("hir_type_unresolved", 0), ("hir_type_i64", 1), ("hir_type_bool", 2),
    ("hir_numeric_policy_none", 0), ("hir_numeric_policy_exact", 1),
    ("hir_numeric_policy_checked", 2),
    ("hir_symbol_none", 0), ("hir_symbol_add", 1),
    ("hir_symbol_subtract", 2), ("hir_symbol_multiply", 3),
    ("hir_symbol_divide", 4), ("hir_symbol_equal", 5),
    ("hir_symbol_not_equal", 6), ("hir_symbol_greater_equal", 7),
    ("hir_symbol_less_equal", 8), ("hir_symbol_greater", 9),
    ("hir_symbol_less", 10),
)


def test_bootstrap_ast_hir_identifier_representation_is_stable(tmp_path):
    project_root = tmp_path / "bootstrap_ast_hir_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(f"print({name}());" for name, _ in AST_HIR_REPRESENTATION)
    (project_root / "src/ast_hir_representation_probe.mrt").write_text(
        "module ast_hir_representation_probe\n"
        "import bootstrap_syntax;\nimport bootstrap_hir;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_path.write_text(manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/ast_hir_representation_probe.mrt"',
    ))
    project = load_project(manifest_path)
    expected = "".join(f"{value}\n" for _, value in AST_HIR_REPRESENTATION)
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


MIR_KIND_REPRESENTATION = (
    ("mir_const_kind", 1), ("mir_binary_kind", 2),
    ("mir_group_alias_kind", 3), ("mir_binding_kind", 4),
    ("composite_const_kind", 1), ("composite_binary_kind", 2),
    ("composite_binding_kind", 3), ("composite_call_kind", 4),
    ("composite_field_kind", 5), ("composite_construct_kind", 6),
    ("composite_operand_kind", 7),
    ("function_mir_kind_function", 1),
    ("function_mir_kind_source_local", 2),
    ("function_mir_kind_temporary_local", 3),
    ("function_mir_kind_const", 4), ("function_mir_kind_binary", 5),
    ("function_mir_kind_copy_to_binding", 6),
    ("function_mir_kind_return", 7), ("function_mir_kind_print", 8),
    ("function_mir_kind_enum_construct", 9),
    ("function_mir_kind_enum_tag_load", 10),
    ("function_mir_kind_enum_payload_load", 11),
    ("function_mir_kind_struct_construct", 12),
    ("function_mir_kind_struct_field_load", 13),
    ("function_mir_kind_struct_field_store", 14),
    ("function_mir_kind_parameter", 15), ("function_mir_kind_call", 16),
    ("function_mir_kind_call_argument", 17),
    ("generic_const_kind", 1), ("generic_call_kind", 2),
    ("generic_operand_kind", 3),
    ("function_contract_temporary_local_kind", 1),
    ("function_contract_const_kind", 2),
    ("function_contract_binary_kind", 3),
    ("function_contract_check_kind", 4),
    ("function_contract_call_kind", 5),
    ("function_contract_result_capture_kind", 6),
    ("function_contract_field_load_kind", 7),
    ("function_contract_old_snapshot_kind", 8),
    ("assembly_source_contract_record_kind", 1),
    ("assembly_source_body_kind", 2),
    ("assembly_source_ownership_kind", 3),
    ("function_contract_precondition_phase", 1),
    ("function_contract_postcondition_phase", 2),
    ("function_contract_entry_snapshot_phase", 3),
)


def test_bootstrap_mir_kind_representation_is_stable(tmp_path):
    project_root = tmp_path / "bootstrap_mir_kind_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(f"print({name}());" for name, _ in MIR_KIND_REPRESENTATION)
    (project_root / "src/mir_kind_representation_probe.mrt").write_text(
        "module mir_kind_representation_probe\n"
        "import bootstrap_mir;\nimport bootstrap_mir_composite;\n"
        "import bootstrap_mir_functions;\nimport bootstrap_mir_generics;\n"
        "import bootstrap_mir_function_contracts;\n"
        "import bootstrap_mir_function_instruction_source;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_path.write_text(manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/mir_kind_representation_probe.mrt"',
    ))
    project = load_project(manifest_path)
    expected = "".join(f"{value}\n" for _, value in MIR_KIND_REPRESENTATION)
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


CFG_STRUCTURED_KIND_REPRESENTATION = (
    ("cfg_block_kind", 10),
    ("cfg_jump_kind", 11),
    ("cfg_branch_kind", 12),
    ("cfg_switch_case_kind", 13),
    ("cfg_switch_default_kind", 14),
    ("cfg_return_kind", 15),
    ("cfg_unreachable_kind", 16),
    ("mir_event_place_kind", 1),
    ("mir_event_return_kind", 2),
    ("mir_event_unreachable_kind", 3),
    ("mir_event_if_kind", 10),
    ("mir_event_else_kind", 11),
    ("mir_event_end_if_kind", 12),
    ("mir_event_begin_while_kind", 19),
    ("mir_event_while_kind", 20),
    ("mir_event_end_while_kind", 21),
    ("mir_event_match_kind", 30),
    ("mir_event_case_kind", 31),
    ("mir_event_default_kind", 32),
    ("mir_event_end_match_kind", 33),
)


def test_bootstrap_cfg_structured_kind_representation_is_stable(tmp_path):
    project_root = tmp_path / "bootstrap_cfg_structured_kind_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(
        f"print({name}());" for name, _ in CFG_STRUCTURED_KIND_REPRESENTATION
    )
    (project_root / "src/cfg_structured_kind_representation_probe.mrt").write_text(
        "module cfg_structured_kind_representation_probe\n"
        "import bootstrap_mir_cfg;\n"
        "import bootstrap_mir_structured_lowering;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_path.write_text(manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/cfg_structured_kind_representation_probe.mrt"',
    ))
    project = load_project(manifest_path)
    expected = "".join(
        f"{value}\n" for _, value in CFG_STRUCTURED_KIND_REPRESENTATION
    )
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


OWNERSHIP_KIND_REPRESENTATION = (
    ("ownership_event_kind_place", 1),
    ("ownership_event_kind_activate", 2),
    ("ownership_event_kind_move", 3),
    ("ownership_event_kind_drop", 4),
    ("ownership_event_kind_replace", 5),
    ("ownership_event_kind_replace_from_binding", 6),
    ("ownership_event_kind_assign", 7),
    ("ownership_event_kind_print", 8),
    ("ownership_event_kind_consume", 9),
    ("ownership_event_kind_return", 10),
    ("ownership_event_kind_end_scope", 11),
    ("ownership_event_kind_use", 12),
    ("ownership_event_kind_end_trivial_scope", 13),
    ("ownership_event_kind_if", 20),
    ("ownership_event_kind_else", 21),
    ("ownership_event_kind_end_if", 22),
    ("ownership_event_kind_begin_while", 29),
    ("ownership_event_kind_while", 30),
    ("ownership_event_kind_end_while", 31),
    ("ownership_event_kind_match", 40),
    ("ownership_event_kind_case", 41),
    ("ownership_event_kind_end_match", 42),
    ("ownership_record_kind_activate", 1),
    ("ownership_record_kind_move", 2),
    ("ownership_record_kind_drop", 3),
    ("ownership_record_kind_replace_drop", 4),
    ("ownership_record_kind_replace_move", 5),
    ("ownership_record_kind_implicit_drop", 6),
    ("ownership_record_kind_nested_transfer", 7),
    ("ownership_state_uninitialized", 0),
    ("ownership_state_live", 1),
    ("ownership_state_moved", 2),
    ("ownership_state_dropped", 3),
)


def test_bootstrap_ownership_kind_representation_is_stable(tmp_path):
    project_root = tmp_path / "bootstrap_ownership_kind_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(
        f"print({name}());" for name, _ in OWNERSHIP_KIND_REPRESENTATION
    )
    (project_root / "src/ownership_kind_representation_probe.mrt").write_text(
        "module ownership_kind_representation_probe\n"
        "import bootstrap_mir_ownership_flow;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_path.write_text(manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/ownership_kind_representation_probe.mrt"',
    ))
    project = load_project(manifest_path)
    expected = "".join(
        f"{value}\n" for _, value in OWNERSHIP_KIND_REPRESENTATION
    )
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


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
