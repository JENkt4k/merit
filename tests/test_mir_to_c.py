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


def test_emits_and_runs_ordered_arithmetic(tmp_path):
    function = MirFunction(
        "answer",
        I64,
        (MirLocal(0, "a", I64), MirLocal(1, "b", I64), MirLocal(2, "sum", I64)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=20),
            MirInstruction(1, "const", result=1, value=22),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="exact"),
        ), MirTerminator("return", operands=(2,))),),
        0,
    )
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


@pytest.mark.parametrize(
    "function,message",
    [
        (MirFunction("bad", MirType("Decimal"), (), (MirBlock(0, (), MirTerminator("return")),), 0), "unsupported MIR type"),
        (MirFunction("bad", I64, (MirLocal(0, "x", I64),), (MirBlock(0, (MirInstruction(0, "call", result=0, symbol="other"),), MirTerminator("return", operands=(0,))),), 0), "unsupported MIR instruction"),
        (MirFunction("bad", I64, (MirLocal(0, "x", I64), MirLocal(1, "y", I64), MirLocal(2, "z", I64)), (MirBlock(0, (MirInstruction(0, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="wrapping"),), MirTerminator("return", operands=(2,))),), 0), "numeric policy"),
    ],
)
def test_unsupported_semantics_fail_closed(function, message):
    with pytest.raises(MirToCError, match=message):
        emit_c_module(scalar_module(function))
