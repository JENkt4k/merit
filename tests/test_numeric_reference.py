import contextlib
import io
import subprocess
from decimal import (
    Decimal,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    localcontext,
)

import pytest

from merit.compiler import Checker, CompileError, Interpreter, compile_file, parse


REFERENCE_ROUNDING = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
    "down": ROUND_DOWN,
    "ceiling": ROUND_CEILING,
    "floor": ROUND_FLOOR,
}


def compile_program(source, tmp_path, name):
    path = tmp_path / f"{name}.mrt"
    executable = tmp_path / name
    path.write_text(source)
    compile_file(path, executable)
    return executable


def run_interpreter(source):
    program = parse(source)
    Checker(program).check()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        Interpreter(program).run()
    return output.getvalue()


def reference_scaled(left, operator, right, rounding, scale=100):
    with localcontext() as context:
        context.prec = 100
        numerator = Decimal(left * right) if operator == "*" else Decimal(left * scale)
        denominator = Decimal(scale) if operator == "*" else Decimal(right)
        return int((numerator / denominator).to_integral_value(rounding=rounding))


def format_scaled(value, scale=100):
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // scale}.{magnitude % scale:02d}"


def test_decimal_matrix_matches_arbitrary_precision_reference_and_native(tmp_path):
    cases = [
        (5, "*", 10),
        (-5, "*", 10),
        (125, "*", 125),
        (-125, "*", 125),
        (100, "/", 800),
        (-100, "/", 800),
        (250, "/", 400),
        (-999, "/", 300),
    ]
    declarations = []
    statements = []
    expected = []
    for policy_index, (policy, rounding) in enumerate(REFERENCE_ROUNDING.items()):
        type_name = f"D{policy_index}"
        declarations.append(f"decimal {type_name}(12,2,{policy});")
        for case_index, (left, operator, right) in enumerate(cases):
            left_name = f"l{policy_index}_{case_index}"
            right_name = f"r{policy_index}_{case_index}"
            statements.extend(
                [
                    f"let {left_name}:{type_name}={format_scaled(left)};",
                    f"let {right_name}:{type_name}={format_scaled(right)};",
                    f"print({left_name}{operator}{right_name});",
                ]
            )
            expected.append(format_scaled(reference_scaled(left, operator, right, rounding)))
    source = "\n".join(
        ["module decimal_reference", *declarations, "fn main()->i32 {", *statements, "return 0;", "}"]
    )
    reference_output = "\n".join(expected) + "\n"
    native = subprocess.run(
        [str(compile_program(source, tmp_path, "decimal_reference"))],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert run_interpreter(source) == native == reference_output
    generated = (tmp_path / "decimal_reference.c").read_text()
    for mode in range(5):
        assert f", 100, {mode}))" in generated
    assert "merit_round_div((__int128)(" in generated
    assert "int64_t _merit_expr_" in generated


def truncate_toward_zero(numerator, denominator):
    magnitude = abs(numerator) // abs(denominator)
    return -magnitude if (numerator < 0) != (denominator < 0) else magnitude


def test_bounded_matrix_matches_unbounded_integer_reference_and_native(tmp_path):
    cases = [
        (299, "+", 1, 300),
        (-299, "-", 1, -300),
        (12, "*", -13, -156),
        (-299, "+", 598, 299),
        (-299, "/", 2, truncate_toward_zero(-299, 2)),
        (299, "/", -2, truncate_toward_zero(299, -2)),
    ]
    statements = []
    for index, (left, operator, right, _) in enumerate(cases):
        statements.extend(
            [
                f"let l{index}:Window={left};",
                f"let r{index}:Window={right};",
                f"print(l{index}{operator}r{index});",
            ]
        )
    source = "\n".join(
        ["module bounded_reference", "bounded Window(i32,-600,600);", "fn main()->i32 {", *statements, "return 0;", "}"]
    )
    reference_output = "".join(f"{result}\n" for *_, result in cases)
    native = subprocess.run(
        [str(compile_program(source, tmp_path, "bounded_reference"))],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert run_interpreter(source) == native == reference_output
    generated = (tmp_path / "bounded_reference.c").read_text()
    assert "merit_check_Window(merit_add_i32(" in generated
    assert "merit_check_Window(merit_sub_i32(" in generated
    assert "merit_check_Window(merit_mul_i32(" in generated
    assert "merit_check_Window(merit_div_i32(" in generated


@pytest.mark.parametrize("operator,right", [("+", 1), ("-", -1), ("*", 2)])
def test_bounded_reference_detects_out_of_domain_results(tmp_path, operator, right):
    source = f"""module bounded_reference_failure
bounded Window(i32,-300,300);
fn main()->i32 {{ let left:Window=300; let right:Window={right}; print(left{operator}right); return 0; }}"""
    program = parse(source)
    Checker(program).check()
    with pytest.raises(RuntimeError, match="bounded overflow in Window"):
        Interpreter(program).run()
    native = subprocess.run(
        [str(compile_program(source, tmp_path, f"bounded_failure_{operator.encode().hex()}"))],
        text=True,
        capture_output=True,
    )
    assert native.returncode == 70
    assert "bounded range violation: Window" in native.stderr


def test_arbitrary_precision_literal_outside_bounded_domain_is_compile_fail():
    source = """module bounded_literal_reference
bounded Window(i64,-300,300);
fn main()->i32 { let value:Window=999999999999999999999999999999999999; return 0; }"""
    program = parse(source)
    with pytest.raises(CompileError, match="outside Window range -300..300"):
        Checker(program).check()
