import shutil
import subprocess

import pytest

from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
)
from merit.bootstrap.mir_to_c import MirToCError, emit_c_module


I64 = MirType("i64")
BOOL = MirType("bool")
UNIT = MirType("unit")


def compile_and_run(tmp_path, module, main_body):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler unavailable")
    source = emit_c_module(module) + "\n" + main_body
    path = tmp_path / "program.c"
    executable = tmp_path / "program"
    path.write_text(source)
    result = subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(path), "-o", str(executable)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return subprocess.run([str(executable)], capture_output=True, text=True)


def scalar_module(function):
    return MirModule("example", (function,))


def constant_function(name, value):
    return MirFunction(
        name,
        I64,
        (MirLocal(0, "value", I64),),
        (MirBlock(0, (MirInstruction(0, "const", result=0, value=value),), MirTerminator("return", operands=(0,))),),
        0,
    )


def binary_function(name, left, right, operator, policy="checked"):
    return MirFunction(
        name,
        I64,
        (MirLocal(0, "left", I64), MirLocal(1, "right", I64), MirLocal(2, "result", I64)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=left),
            MirInstruction(1, "const", result=1, value=right),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol=operator, numeric_policy=policy),
        ), MirTerminator("return", operands=(2,))),),
        0,
    )


def test_emits_and_runs_ordered_arithmetic(tmp_path):
    function = binary_function("answer", 20, 22, "+", policy="exact")
    generated = emit_c_module(scalar_module(function))
    assert generated.index("m0 = INT64_C(20)") < generated.index("m1 = INT64_C(22)") < generated.index("m2 = m0 + m1")
    run = compile_and_run(tmp_path, scalar_module(function), "int main(void) { return answer() == 42 ? 0 : 1; }")
    assert run.returncode == 0


def test_emits_if_else_blocks(tmp_path):
    function = MirFunction(
        "choose",
        I64,
        (MirLocal(0, "condition", BOOL), MirLocal(1, "result", I64)),
        (
            MirBlock(0, (MirInstruction(0, "const", result=0, value=True),), MirTerminator("branch", operands=(0,), targets=(1, 2))),
            MirBlock(1, (MirInstruction(1, "const", result=1, value=7),), MirTerminator("jump", targets=(3,))),
            MirBlock(2, (MirInstruction(2, "const", result=1, value=9),), MirTerminator("jump", targets=(3,))),
            MirBlock(3, (), MirTerminator("return", operands=(1,))),
        ),
        0,
    )
    run = compile_and_run(tmp_path, scalar_module(function), "int main(void) { return choose() == 7 ? 0 : 1; }")
    assert run.returncode == 0


def test_emits_loop_back_edge(tmp_path):
    function = MirFunction(
        "count",
        I64,
        (
            MirLocal(0, "value", I64), MirLocal(1, "limit", I64),
            MirLocal(2, "condition", BOOL), MirLocal(3, "one", I64), MirLocal(4, "next", I64),
        ),
        (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=0),
                MirInstruction(1, "const", result=1, value=3),
                MirInstruction(2, "const", result=3, value=1),
            ), MirTerminator("jump", targets=(1,))),
            MirBlock(1, (MirInstruction(3, "binary", result=2, operands=(0, 1), symbol="<", numeric_policy="exact"),), MirTerminator("branch", operands=(2,), targets=(2, 3))),
            MirBlock(2, (
                MirInstruction(4, "binary", result=4, operands=(0, 3), symbol="+", numeric_policy="exact"),
                MirInstruction(5, "copy", result=0, operands=(4,)),
            ), MirTerminator("jump", targets=(1,))),
            MirBlock(3, (), MirTerminator("return", operands=(0,))),
        ),
        0,
    )
    run = compile_and_run(tmp_path, scalar_module(function), "int main(void) { return count() == 3 ? 0 : 1; }")
    assert run.returncode == 0


def test_emits_print_in_instruction_order(tmp_path):
    function = MirFunction(
        "show",
        I64,
        (MirLocal(0, "value", I64),),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=42),
            MirInstruction(1, "print", operands=(0,)),
        ), MirTerminator("return", operands=(0,))),),
        0,
    )
    module = scalar_module(function)
    generated = emit_c_module(module)
    assert "#include <stdio.h>" in generated
    assert generated.index("m0 = INT64_C(42)") < generated.index('printf("%lld\\n", (long long)m0)')
    run = compile_and_run(tmp_path, module, "int main(void) { return show() == 42 ? 0 : 1; }")
    assert run.returncode == 0
    assert run.stdout == "42\n"


def test_emits_switch_in_case_order(tmp_path):
    function = MirFunction(
        "classify",
        I64,
        (MirLocal(0, "key", I64), MirLocal(1, "result", I64)),
        (
            MirBlock(0, (MirInstruction(0, "const", result=0, value=2),), MirTerminator("switch", operands=(0,), targets=(1, 2, 3), cases=(1, 2))),
            MirBlock(1, (MirInstruction(1, "const", result=1, value=10),), MirTerminator("jump", targets=(4,))),
            MirBlock(2, (MirInstruction(2, "const", result=1, value=20),), MirTerminator("jump", targets=(4,))),
            MirBlock(3, (MirInstruction(3, "const", result=1, value=30),), MirTerminator("jump", targets=(4,))),
            MirBlock(4, (), MirTerminator("return", operands=(1,))),
        ),
        0,
    )
    generated = emit_c_module(scalar_module(function))
    assert generated.index("case 1") < generated.index("case 2") < generated.index("default")
    run = compile_and_run(tmp_path, scalar_module(function), "int main(void) { return classify() == 20 ? 0 : 1; }")
    assert run.returncode == 0


def test_output_is_deterministic():
    function = MirFunction("empty", UNIT, (), (MirBlock(0, (), MirTerminator("return")),), 0)
    module = scalar_module(function)
    assert emit_c_module(module) == emit_c_module(module)


def test_contract_and_capability_checks_are_explicit():
    function = MirFunction(
        "guarded",
        UNIT,
        (MirLocal(0, "condition", BOOL),),
        (MirBlock(0, (
            MirInstruction(0, "capability_check", capabilities=("filesystem.read",)),
            MirInstruction(1, "const", result=0, value=True),
            MirInstruction(2, "contract_check", operands=(0,), contract_kind="precondition"),
        ), MirTerminator("return")),),
        0,
    )
    generated = emit_c_module(scalar_module(function))
    assert 'merit_capability_check("filesystem.read")' in generated
    assert 'merit_contract_failure("precondition")' in generated


def test_emits_forward_prototypes_and_runs_multi_function_call(tmp_path):
    caller = MirFunction(
        "caller",
        I64,
        (MirLocal(0, "called", I64),),
        (MirBlock(0, (MirInstruction(0, "call", result=0, symbol="callee"),), MirTerminator("return", operands=(0,))),),
        0,
    )
    callee = constant_function("callee", 42)
    module = MirModule("calls", (caller, callee))
    generated = emit_c_module(module)
    assert generated.index("int64_t caller(void);") < generated.index("int64_t caller(void) {")
    assert generated.index("int64_t callee(void);") < generated.index("int64_t caller(void) {")
    assert "m0 = callee();" in generated
    run = compile_and_run(tmp_path, module, "int main(void) { return caller() == 42 ? 0 : 1; }")
    assert run.returncode == 0


def test_emits_unit_call_without_result(tmp_path):
    callee = MirFunction("touch", UNIT, (), (MirBlock(0, (), MirTerminator("return")),), 0)
    caller = MirFunction(
        "invoke",
        UNIT,
        (),
        (MirBlock(0, (MirInstruction(0, "call", symbol="touch"),), MirTerminator("return")),),
        0,
    )
    module = MirModule("unit_call", (caller, callee))
    generated = emit_c_module(module)
    assert "touch();" in generated
    run = compile_and_run(tmp_path, module, "int main(void) { invoke(); return 0; }")
    assert run.returncode == 0


@pytest.mark.parametrize(
    "operator,left,right,expected,helper",
    [
        ("+", 20, 22, 42, "merit_checked_add_i64"),
        ("-", 50, 8, 42, "merit_checked_sub_i64"),
        ("*", 6, 7, 42, "merit_checked_mul_i64"),
        ("/", 84, 2, 42, "merit_checked_div_i64"),
        ("%", 44, 43, 1, "merit_checked_rem_i64"),
    ],
)
def test_checked_i64_operations_compile_and_run(tmp_path, operator, left, right, expected, helper):
    function = binary_function("checked", left, right, operator)
    module = scalar_module(function)
    generated = emit_c_module(module)
    assert f"m2 = {helper}(m0, m1);" in generated
    run = compile_and_run(tmp_path, module, f"int main(void) {{ return checked() == {expected} ? 0 : 1; }}")
    assert run.returncode == 0


@pytest.mark.parametrize(
    "operator,left,right",
    [
        ("+", 2**63 - 1, 1),
        ("-", -(2**63), 1),
        ("*", 2**62, 4),
        ("/", -(2**63), -1),
        ("%", 1, 0),
    ],
)
def test_checked_i64_failures_abort_deterministically(tmp_path, operator, left, right):
    function = binary_function("overflow", left, right, operator)
    run = compile_and_run(tmp_path, scalar_module(function), "int main(void) { (void)overflow(); return 0; }")
    assert run.returncode != 0


def test_checked_helpers_are_emitted_only_when_used():
    exact = emit_c_module(scalar_module(binary_function("exact", 1, 2, "+", policy="exact")))
    checked = emit_c_module(scalar_module(binary_function("checked", 1, 2, "+")))
    assert "merit_numeric_failure" not in exact
    assert "merit_checked_add_i64" not in exact
    assert "merit_checked_add_i64" in checked
    assert "merit_checked_mul_i64" not in checked


def test_int64_min_literal_is_portable(tmp_path):
    function = constant_function("minimum", -(2**63))
    generated = emit_c_module(scalar_module(function))
    assert "m0 = INT64_MIN;" in generated
    run = compile_and_run(tmp_path, scalar_module(function), "int main(void) { return minimum() == INT64_MIN ? 0 : 1; }")
    assert run.returncode == 0


@pytest.mark.parametrize(
    "module,message",
    [
        (scalar_module(MirFunction("bad", MirType("Decimal"), (), (MirBlock(0, (), MirTerminator("return")),), 0)), "unsupported MIR type"),
        (scalar_module(MirFunction("bad", I64, (MirLocal(0, "x", I64), MirLocal(1, "y", I64), MirLocal(2, "z", I64)), (MirBlock(0, (MirInstruction(0, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="wrapping"),), MirTerminator("return", operands=(2,))),), 0)), "numeric policy"),
        (MirModule("bad", (MirFunction("caller", I64, (MirLocal(0, "x", I64),), (MirBlock(0, (MirInstruction(0, "call", result=0, symbol="missing"),), MirTerminator("return", operands=(0,))),), 0),)), "unknown MIR function"),
        (MirModule("bad", (constant_function("a-b", 1), constant_function("a_b", 2))), "collide as C identifier"),
    ],
)
def test_unsupported_semantics_fail_closed(module, message):
    with pytest.raises(MirToCError, match=message):
        emit_c_module(module)


def test_value_call_requires_result_local():
    callee = constant_function("callee", 1)
    caller = MirFunction("caller", UNIT, (), (MirBlock(0, (MirInstruction(0, "call", symbol="callee"),), MirTerminator("return")),), 0)
    with pytest.raises(MirToCError, match="require a result local"):
        emit_c_module(MirModule("bad", (caller, callee)))


def test_unit_call_rejects_result_local():
    callee = MirFunction("callee", UNIT, (), (MirBlock(0, (), MirTerminator("return")),), 0)
    caller = MirFunction(
        "caller",
        I64,
        (MirLocal(0, "result", I64),),
        (MirBlock(0, (MirInstruction(0, "call", result=0, symbol="callee"),), MirTerminator("return", operands=(0,))),),
        0,
    )
    with pytest.raises(MirToCError, match="cannot produce a result"):
        emit_c_module(MirModule("bad", (caller, callee)))


def test_core_calls_reject_arguments_until_parameter_contract_exists():
    callee = constant_function("callee", 1)
    caller = MirFunction(
        "caller",
        I64,
        (MirLocal(0, "argument", I64), MirLocal(1, "result", I64)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=1),
            MirInstruction(1, "call", result=1, operands=(0,), symbol="callee"),
        ), MirTerminator("return", operands=(1,))),),
        0,
    )
    with pytest.raises(MirToCError, match="only no-argument"):
        emit_c_module(MirModule("bad", (caller, callee)))


def test_out_of_range_i64_literal_is_rejected():
    function = constant_function("too_large", 2**63)
    with pytest.raises(MirToCError, match="out of range"):
        emit_c_module(scalar_module(function))
