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
    ("function_mir_absent_record_value", -1),
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
    ("assembly_source_absent_record_value", -1),
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

OWNERSHIP_SENTINEL_REPRESENTATION = (
    ("ownership_binding_not_found", -1),
    ("ownership_record_no_instruction_id", -1),
    ("ownership_record_no_other_binding_id", -1),
    ("ownership_event_no_local_id", -1),
    ("ownership_frame_no_branch_start", -1),
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


def test_bootstrap_ownership_sentinel_representation_is_stable(tmp_path):
    project_root = tmp_path / "bootstrap_ownership_sentinel_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(
        f"print({name}());" for name, _ in OWNERSHIP_SENTINEL_REPRESENTATION
    )
    (project_root / "src/ownership_sentinel_representation_probe.mrt").write_text(
        "module ownership_sentinel_representation_probe\n"
        "import bootstrap_mir_ownership_flow;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_path.write_text(manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/ownership_sentinel_representation_probe.mrt"',
    ))
    project = load_project(manifest_path)
    expected = "".join(
        f"{value}\n" for _, value in OWNERSHIP_SENTINEL_REPRESENTATION
    )
    assert interpret(project) == expected
    _, _, executable = build(project, project_root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected


STATUS_NAMESPACE_REPRESENTATION = (
    ("statement_record_return_kind()", 22),
    ("statement_record_drop_kind()", 24),
    ("statement_record_match_kind()", 27),
    ("statement_record_with_kind()", 28),
    ("statement_record_replace_kind()", 29),
    ("clause_effects_kind()", 11),
    ("clause_requires_caps_kind()", 12),
    ("clause_requires_kind()", 13),
    ("clause_ensures_kind()", 14),
    ("clause_metadata_effect_kind()", 1),
    ("clause_metadata_capability_kind()", 2),
    ("capability_effect_enter_kind()", 1),
    ("capability_effect_exit_kind()", 2),
    ("source_expression_unresolved_binding_failure()", -1),
    ("source_expression_invalid_borrow_failure()", -5),
    ("function_mir_too_few_records_status()", 1),
    ("function_mir_invalid_header_kind_status()", 2),
    ("function_mir_invalid_header_span_status()", 3),
    ("function_mir_invalid_header_symbol_status()", 4),
    ("function_mir_invalid_header_type_status()", 5),
    ("function_mir_record_after_return_status()", 6),
    ("function_mir_invalid_source_local_id_status()", 7),
    ("function_mir_invalid_source_local_span_status()", 8),
    ("function_mir_invalid_source_local_type_status()", 9),
    ("function_mir_invalid_source_local_binding_status()", 10),
    ("function_mir_invalid_source_local_mutability_status()", 11),
    ("function_mir_invalid_temporary_id_status()", 12),
    ("function_mir_invalid_temporary_type_status()", 13),
    ("function_mir_invalid_temporary_hir_status()", 14),
    ("function_mir_invalid_const_id_status()", 15),
    ("function_mir_invalid_const_result_status()", 16),
    ("function_mir_invalid_const_span_status()", 17),
    ("function_mir_invalid_const_type_status()", 18),
    ("function_mir_invalid_const_hir_status()", 19),
    ("function_mir_invalid_binary_id_status()", 20),
    ("function_mir_invalid_binary_operand_status()", 21),
    ("function_mir_invalid_binary_symbol_status()", 22),
    ("function_mir_invalid_binary_type_status()", 23),
    ("function_mir_invalid_binary_policy_status()", 24),
    ("function_mir_invalid_binary_hir_status()", 25),
    ("function_mir_invalid_copy_id_status()", 26),
    ("function_mir_invalid_copy_operand_status()", 27),
    ("function_mir_invalid_copy_binding_status()", 28),
    ("function_mir_invalid_copy_hir_status()", 29),
    ("function_mir_invalid_return_operand_status()", 30),
    ("function_mir_invalid_return_hir_status()", 31),
    ("function_mir_unknown_record_kind_status()", 32),
    ("function_mir_missing_return_status()", 33),
    ("function_mir_invalid_print_id_status()", 34),
    ("function_mir_invalid_print_operand_status()", 35),
    ("function_mir_invalid_print_hir_status()", 36),
    ("function_mir_invalid_enum_id_status()", 37),
    ("function_mir_invalid_enum_operand_status()", 38),
    ("function_mir_invalid_enum_hir_status()", 39),
    ("function_mir_invalid_enum_type_status()", 40),
    ("function_mir_invalid_enum_symbol_status()", 41),
    ("function_mir_invalid_struct_record_status()", 42),
    ("function_mir_invalid_callable_header_status()", 43),
    ("function_mir_invalid_parameter_status()", 44),
    ("function_mir_invalid_call_status()", 45),
    ("function_mir_invalid_call_argument_status()", 46),
    ("function_mir_parameter_count_mismatch_status()", 47),
    ("sfr_signature_missing_header_status()", 1),
    ("sfr_signature_invalid_name_status()", 2),
    ("sfr_signature_missing_parameter_list_status()", 3),
    ("sfr_signature_invalid_parameter_status()", 4),
    ("sfr_signature_unresolved_parameter_type_status()", 5),
    ("sfr_signature_unclosed_parameter_list_status()", 6),
    ("sfr_signature_missing_return_status()", 7),
    ("sfr_signature_unresolved_return_type_status()", 8),
    ("sfr_signature_unresolved_borrow_origin_status()", 9),
    ("sfr_signature_owned_borrow_origin_status()", 10),
    ("sfr_signature_mutable_origin_required_status()", 11),
    ("sfr_signature_inconsistent_borrow_origin_status()", 12),
    ("sfr_signature_invalid_body_status()", 13),
    ("sfr_vector_unresolved_type_status()", 14),
    ("sfr_vector_get_owned_element_status()", 15),
    ("sfr_vector_set_owned_element_status()", 16),
    ("sfr_vector_replace_copy_element_status()", 17),
    ("sfr_duplicate_current_signature_ownership_status()", 20),
    ("sfr_missing_current_signature_ownership_status()", 21),
    ("sfr_parameter_spans_missing_header_status()", 1),
    ("sfr_parameter_spans_missing_open_status()", 2),
    ("sfr_parameter_spans_invalid_parameter_status()", 3),
    ("sfr_parameter_spans_unclosed_status()", 4),
    ("sfr_invalid_numeric_descriptor_status()", 1),
    ("sfr_unresolved_struct_descriptor_status()", 1),
    ("sfr_unresolved_vector_descriptor_status()", 2),
    ("sfr_invalid_function_header_status()", 1),
    ("sfr_missing_let_binding_status()", 2),
    ("sfr_missing_var_binding_status()", 3),
    ("sfr_missing_let_type_status()", 4),
    ("sfr_missing_var_type_status()", 5),
    ("sfr_invalid_let_expression_status()", 10),
    ("sfr_invalid_var_expression_status()", 12),
    ("sfr_invalid_return_expression_status()", 14),
    ("sfr_invalid_if_expression_status()", 16),
    ("sfr_invalid_while_expression_status()", 18),
    ("sfr_invalid_assignment_operands_status()", 20),
    ("sfr_invalid_assignment_target_status()", 21),
    ("sfr_invalid_assignment_value_status()", 22),
    ("sfr_invalid_expression_statement_status()", 23),
    ("sfr_invalid_expression_result_status()", 24),
    ("sfr_invalid_print_expression_status()", 25),
    ("sfr_invalid_drop_operand_status()", 27),
    ("sfr_invalid_drop_expression_status()", 28),
    ("sfr_expression_invalid_struct_symbol_status()", 62),
    ("sfr_expression_unresolved_struct_type_status()", 63),
    ("sfr_expression_missing_struct_initializer_status()", 64),
    ("sfr_expression_invalid_struct_initializer_status()", 65),
    ("sfr_expression_invalid_struct_receiver_status()", 66),
    ("sfr_expression_unresolved_struct_receiver_status()", 67),
    ("sfr_expression_unknown_failure_status()", 68),
    ("sfr_borrowed_value_storage_status()", 69),
    ("sfr_duplicate_current_signature_status()", 79),
    ("sfr_missing_current_signature_status()", 80),
    ("sfr_try_result_shape_status()", 81),
    ("sfr_ownership_binding_order_status()", 82),
    ("sfr_expression_call_argument_count_status()", 90),
    ("resolved_pipeline_duplicate_allocate_capability_status()", 1),
    ("resolved_pipeline_unauthorized_allocation_status()", 2),
    ("resolved_pipeline_return_count_mismatch_status()", 1),
    ("sfr_expression_call_argument_expression_status()", 91),
    ("sfr_expression_call_argument_type_status()", 92),
    ("sfr_expression_borrowed_argument_by_value_status()", 93),
    ("sfr_expression_move_while_loaned_status()", 94),
    ("sfr_expression_unresolved_borrow_root_status()", 95),
    ("sfr_expression_shared_to_mutable_borrow_status()", 96),
    ("sfr_expression_immutable_mutable_borrow_status()", 97),
    ("sfr_expression_borrow_of_moved_value_status()", 98),
    ("sfr_expression_conflicting_loan_status()", 99),
    ("sfr_expression_invalid_call_callee_status()", 100),
    ("sfr_expression_unresolved_call_or_variant_status()", 101),
    ("sfr_expression_conflicting_numeric_domain_status()", 102),
    ("sfr_expression_unresolved_variant_status()", 103),
    ("sfr_callable_catalog_status(7)", 17),
    ("sfr_function_signature_status(7)", 77),
    ("sfr_parameter_ownership_status(7)", 87),
    ("lower_resolved_source_function_semantics_catalog_failure_status(7)", 377),
    ("resolved_pipeline_function_failure_status(7)", 207),
    ("resolved_pipeline_match_arm_failure_status(7)", 307),
    ("resolved_pipeline_capability_scope_record_failure_status(7)", 407),
    ("resolved_pipeline_match_identity_failure_status(7)", 507),
    ("resolved_pipeline_match_resolution_failure_status(7)", 527),
    ("resolved_pipeline_match_identity_resolution_failure_status(7)", 27),
    ("resolved_pipeline_capability_scope_resolution_failure_status(7)", 607),
    ("resolved_pipeline_allocation_capability_failure_status(7)", 657),
    ("resolved_pipeline_ownership_source_failure_status(7)", 707),
    ("resolved_pipeline_ownership_flow_failure_status(7)", 807),
    ("resolved_pipeline_ownership_validation_failure_status(7)", 907),
    ("resolved_pipeline_return_surface_failure_status(7)", 1007),
    ("resolved_pipeline_unresolved_local_type_status()", 201),
    ("resolved_parameter_metadata_status(7)", 87),
    ("lower_resolved_source_function_assembly_catalog_failure_status(7)", 1377),
    ("resolved_assembly_semantic_failure_status(7)", 1007),
    ("resolved_assembly_stats_failure_status(7)", 2007),
    ("resolved_assembly_invalid_stats_status()", 2005),
    ("resolved_assembly_missing_return_status()", 2006),
    ("resolved_assembly_plan_failure_status(7)", 3007),
    ("resolved_assembly_event_failure_status(7)", 4007),
    ("resolved_assembly_cfg_failure_status(7)", 5007),
    ("resolved_assembly_invalid_sources_status()", 6001),
    ("resolved_assembly_placement_count_status()", 6002),
    ("lower_resolved_source_function_assembly_from_source_types_catalog_failure_status(7)", 97),
    ("resolved_source_types_metadata_failure_status(7)", 107),
    ("resolved_source_types_assembly_failure_status(7)", 1007),
    ("resolved_source_types_binding_validation_failure_status(7)", 8007),
    ("lower_resolved_source_function_assembly_from_source_tokens_catalog_failure_status(7)", 1097),
    ("resolved_source_tokens_type_failure_status(7)", 57),
    ("resolved_source_tokens_assembly_failure_status(7)", 1007),
    ("source_function_body_failure_status(7)", 107),
    ("source_function_binding_order_status()", 201),
    ("source_function_metadata_failure_status(7)", 307),
    ("source_function_metadata_validation_failure_status(7)", 407),
    ("source_function_contract_failure_status(7)", 507),
    ("source_function_contract_validation_failure_status(7)", 607),
    ("native_driver_missing_function_status()", 901),
    ("native_driver_unopened_function_body_status()", 902),
    ("native_driver_unclosed_function_body_status()", 903),
    ("native_driver_invalid_function_slice_status()", 904),
    ("native_driver_unclosed_function_slice_status()", 905),
    ("native_driver_function_count_mismatch_status()", 906),
    ("native_driver_enum_catalog_failure_status(7)", 927),
    ("native_driver_capability_catalog_failure_status(7)", 957),
    ("native_driver_numeric_descriptor_failure_status(7)", 992),
    ("native_driver_assembly_failure_status(7)", 1007),
    ("native_driver_bundle_header_failure_status(7)", 2007),
    ("native_driver_bundle_item_failure_status(7)", 3007),
    ("native_driver_callable_catalog_failure_status(7)", 2097),
    ("ownership_status_empty_event_stream()", 1),
    ("ownership_status_invalid_binding_id()", 2),
    ("ownership_status_invalid_binding_local()", 3),
    ("ownership_status_invalid_owned_flag()", 4),
    ("ownership_status_invalid_mutable_flag()", 5),
    ("ownership_status_place_after_termination()", 20),
    ("ownership_status_move_destination_initialized()", 30),
    ("ownership_status_drop_after_termination()", 31),
    ("ownership_status_invalid_replace_local()", 40),
    ("ownership_status_return_after_termination()", 41),
    ("ownership_status_while_wrong_frame()", 56),
    ("ownership_status_if_without_else_diverged()", 61),
    ("ownership_status_unclosed_control_frame()", 65),
    ("ownership_status_missing_replace_target()", 66),
    ("ownership_status_replace_source_not_live()", 73),
    ("ownership_status_replace_binding_after_termination()", 74),
    ("ownership_status_incomplete_match_cases()", 85),
    ("ownership_status_assign_after_termination()", 90),
    ("ownership_status_scope_binding_uninitialized()", 104),
    ("ownership_status_live_at_scope_exit()", 105),
    ("ownership_status_use_binding_not_live()", 108),
    ("ownership_record_status_invalid_kind()", 1),
    ("ownership_record_status_nested_transfer_has_instruction()", 10),
    ("source_control_missing_binding_status()", 10),
    ("source_control_invalid_return_expression_status()", 20),
    ("source_control_invalid_assign_value_status()", 39),
    ("source_control_missing_scope_binding_status()", 45),
    ("source_control_invalid_match_arm_count_status()", 50),
    ("source_control_expression_failure_status(-1)", 61),
    ("source_control_expression_failure_status(-5)", 65),
    ("source_control_expression_failure_status(-9)", 66),
    ("source_control_missing_drop_operand_status()", 67),
    ("source_control_invalid_try_value_status()", 73),
    ("source_control_match_without_arms_status()", 127),
    ("source_control_missing_capability_scope_status()", 128),
    ("source_control_unknown_statement_status(31)", 131),
    ("source_function_stats_empty_records_status()", 1),
    ("source_function_stats_invalid_record_kind_status()", 14),
    ("resolved_control_invalid_value_status()", 30),
    ("resolved_control_invalid_variant_status()", 33),
    ("function_contract_record_invalid_kind_status()", 10),
    ("function_contract_record_invalid_old_snapshot_status()", 20),
    ("function_contract_missing_ast_status()", 20),
    ("function_contract_numeric_type_mismatch_status()", 33),
    ("clause_metadata_invalid_kind_status()", 10),
    ("clause_metadata_invalid_semantic_id_status()", 14),
    ("structured_status_place_after_termination()", 2),
    ("structured_status_duplicate_else()", 10),
    ("structured_status_missing_default()", 30),
    ("structured_status_missing_terminator()", 34),
    ("structured_status_missing_while_condition()", 41),
    ("statement_lower_missing_let_expression_status()", 10),
    ("statement_lower_invalid_print_expression_status()", 25),
    ("statement_lower_unclosed_frame_status()", 32),
    ("statement_lower_unknown_kind_status(31)", 131),
    ("match_resolution_arm_order_status()", 1),
    ("match_identity_empty_match_status()", 25),
    ("capability_resolution_unknown_capability_status()", 11),
    ("match_merge_empty_arms_status()", 1),
    ("match_merge_state_divergence_status()", 9),
    ("capability_effect_invalid_capability_status()", 21),
    ("function_assembly_invalid_binding_count_status()", 1),
    ("function_assembly_body_instruction_order_status()", 40),
    ("assembly_plan_invalid_binding_count_status()", 1),
    ("assembly_contract_validation_status(7)", 407),
    ("ownership_assembly_invalid_binding_count_status()", 1),
    ("ownership_assembly_body_instruction_count_status()", 46),
    ("ownership_assembly_empty_event_stream_status()", 104),
    ("match_structure_missing_open_status()", 10),
    ("match_structure_missing_arrow_status()", 17),
    ("match_structure_empty_subject_status()", 24),
    ("composite_validation_empty_status()", 1),
    ("composite_validation_invalid_construct_status()", 10),
    ("hir_validation_empty_status()", 1),
    ("hir_validation_invalid_call_or_field_status()", 9),
    ("hir_validation_invalid_field_initializer_status()", 13),
    ("assembly_source_global_order_status()", 1),
    ("assembly_source_unexpected_contract_metadata_status()", 6),
    ("hir_string_validation_invalid_kind_status()", 1),
    ("hir_string_validation_invalid_policy_status()", 5),
    ("expression_validity_structure_status()", 1),
    ("expression_validity_requested_span_status()", 4),
    ("ownership_metadata_invalid_type_catalog_status()", 1),
    ("ownership_metadata_unresolved_declared_type_status()", 4),
    ("ownership_metadata_validation_count_status()", 5),
    ("source_binding_collection_missing_operand_status()", 1),
    ("source_binding_collection_local_id_status()", 4),
    ("generic_validation_empty_status()", 1),
    ("generic_validation_missing_specialization_status()", 8),
    ("source_type_lifecycle_missing_declared_type_status()", 1),
    ("source_type_lifecycle_unresolved_status()", 3),
    ("mir_validation_empty_status()", 1),
    ("mir_validation_invalid_binding_status()", 8),
    ("ast_validation_invalid_span_status()", 1),
    ("ast_validation_empty_status()", 8),
)


def test_bootstrap_status_namespace_representation_is_stable(tmp_path):
    project_root = tmp_path / "bootstrap_status_namespace_representation"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    lexer_source, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer_source)
    prints = " ".join(
        f"print({expression});" for expression, _ in STATUS_NAMESPACE_REPRESENTATION
    )
    (project_root / "src/status_namespace_representation_probe.mrt").write_text(
        "module status_namespace_representation_probe\n"
        "import bootstrap_mir_functions;\n"
        "import bootstrap_mir_source_function_records;\n"
        "import bootstrap_mir_source_function_pipeline;\n"
        "import bootstrap_mir_resolved_source_function_pipeline;\n"
        "import bootstrap_mir_resolved_source_function_assembly;\n"
        "import bootstrap_mir_ownership_flow;\n"
        "import bootstrap_mir_source_ownership_control;\n"
        "import bootstrap_mir_source_function_record_stats;\n"
        "import bootstrap_mir_resolved_control_flow;\n"
        "import bootstrap_mir_function_contracts;\n"
        "import bootstrap_mir_function_clause_metadata;\n"
        "import bootstrap_mir_structured_lowering;\n"
        "import bootstrap_mir_statement_lowering;\n"
        "import bootstrap_statement_semantics;\n"
        "import bootstrap_mir_match_capability_flow;\n"
        "import bootstrap_mir_function_assembly;\n"
        "import bootstrap_mir_function_assembly_plan;\n"
        "import bootstrap_mir_function_ownership_assembly;\n"
        "import bootstrap_statement_structure;\n"
        "import bootstrap_mir_composite;\n"
        "import bootstrap_hir;\n"
        "import bootstrap_mir_function_instruction_source;\n"
        "import bootstrap_hir_strings;\n"
        "import bootstrap_expression_validity;\n"
        "import bootstrap_mir_source_ownership_metadata;\n"
        "import bootstrap_mir_source_ownership_expression;\n"
        "import bootstrap_mir_generics;\n"
        "import bootstrap_mir_source_type_lifecycle;\n"
        "import bootstrap_mir;\n"
        "import bootstrap_syntax;\n"
        "import bootstrap_native_replacement_driver;\n"
        f"fn main()->i32 {{ {prints} return 0; }}\n"
    )
    manifest_path = project_root / "Merit.toml"
    manifest_path.write_text(manifest_path.read_text().replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/status_namespace_representation_probe.mrt"',
    ))
    project = load_project(manifest_path)
    expected = "".join(
        f"{value}\n" for _, value in STATUS_NAMESPACE_REPRESENTATION
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
