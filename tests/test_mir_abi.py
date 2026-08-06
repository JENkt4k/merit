import json
import shutil
import subprocess

import pytest

from merit.bootstrap.mir_abi import (
    MIR_ABI_SCHEMA,
    MirAbiError,
    MirAbiModule,
    MirFunctionSignature,
    MirParameter,
    canonical_mir_abi_json,
    parse_mir_abi,
)
from merit.bootstrap.mir_abi_to_c import MirAbiToCError, emit_c_abi_module
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
)

I64 = MirType("i64")
BOOL = MirType("bool")
UNIT = MirType("unit")


def compile_and_run(tmp_path, abi, main_body):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler unavailable")
    source = emit_c_abi_module(abi) + "\n" + main_body
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


def binary_function(name="add"):
    return MirFunction(
        name,
        I64,
        (
            MirLocal(0, "left", I64),
            MirLocal(1, "right", I64),
            MirLocal(2, "result", I64),
        ),
        (
            MirBlock(
                0,
                (
                    MirInstruction(
                        0,
                        "binary",
                        result=2,
                        operands=(0, 1),
                        symbol="+",
                        numeric_policy="checked",
                    ),
                ),
                MirTerminator("return", operands=(2,)),
            ),
        ),
        0,
    )


def binary_signature(name="add", exported_name=None):
    return MirFunctionSignature(
        name,
        (
            MirParameter("left", 0, I64),
            MirParameter("right", 1, I64),
        ),
        exported_name,
    )


def test_abi_canonical_round_trip():
    abi = MirAbiModule(
        MirModule("math", (binary_function(),)),
        (binary_signature(exported_name="merit_add_i64"),),
    )
    encoded = canonical_mir_abi_json(abi)
    assert encoded == canonical_mir_abi_json(abi)
    assert parse_mir_abi(json.loads(encoded)) == abi
    assert json.loads(encoded)["schema"] == MIR_ABI_SCHEMA


def test_two_argument_native_call(tmp_path):
    add = binary_function()
    caller = MirFunction(
        "answer",
        I64,
        (
            MirLocal(0, "twenty", I64),
            MirLocal(1, "twenty_two", I64),
            MirLocal(2, "result", I64),
        ),
        (
            MirBlock(
                0,
                (
                    MirInstruction(0, "const", result=0, value=20),
                    MirInstruction(1, "const", result=1, value=22),
                    MirInstruction(2, "call", result=2, operands=(0, 1), symbol="add"),
                ),
                MirTerminator("return", operands=(2,)),
            ),
        ),
        0,
    )
    abi = MirAbiModule(
        MirModule("math", (caller, add)),
        (MirFunctionSignature("answer"), binary_signature()),
    )
    generated = emit_c_abi_module(abi)
    assert "int64_t add(int64_t p0, int64_t p1);" in generated
    assert "int64_t m0 = p0;" in generated
    assert "int64_t m1 = p1;" in generated
    assert "m2 = add(m0, m1);" in generated
    run = compile_and_run(
        tmp_path,
        abi,
        "int main(void) { return answer() == 42 ? 0 : 1; }",
    )
    assert run.returncode == 0


def test_argument_order_is_preserved(tmp_path):
    subtract = MirFunction(
        "subtract",
        I64,
        (
            MirLocal(0, "left", I64),
            MirLocal(1, "right", I64),
            MirLocal(2, "result", I64),
        ),
        (
            MirBlock(
                0,
                (
                    MirInstruction(
                        0,
                        "binary",
                        result=2,
                        operands=(0, 1),
                        symbol="-",
                        numeric_policy="checked",
                    ),
                ),
                MirTerminator("return", operands=(2,)),
            ),
        ),
        0,
    )
    caller = MirFunction(
        "ordered",
        I64,
        (MirLocal(0, "a", I64), MirLocal(1, "b", I64), MirLocal(2, "out", I64)),
        (
            MirBlock(
                0,
                (
                    MirInstruction(0, "const", result=0, value=50),
                    MirInstruction(1, "const", result=1, value=8),
                    MirInstruction(2, "call", result=2, operands=(0, 1), symbol="subtract"),
                ),
                MirTerminator("return", operands=(2,)),
            ),
        ),
        0,
    )
    abi = MirAbiModule(
        MirModule("ordered", (caller, subtract)),
        (
            MirFunctionSignature("ordered"),
            MirFunctionSignature(
                "subtract",
                (MirParameter("left", 0, I64), MirParameter("right", 1, I64)),
            ),
        ),
    )
    run = compile_and_run(
        tmp_path,
        abi,
        "int main(void) { return ordered() == 42 ? 0 : 1; }",
    )
    assert run.returncode == 0


def test_bool_parameter_and_unit_call(tmp_path):
    consume = MirFunction(
        "consume",
        UNIT,
        (MirLocal(0, "flag", BOOL),),
        (MirBlock(0, (), MirTerminator("return")),),
        0,
    )
    caller = MirFunction(
        "invoke",
        UNIT,
        (MirLocal(0, "flag", BOOL),),
        (
            MirBlock(
                0,
                (
                    MirInstruction(0, "const", result=0, value=True),
                    MirInstruction(1, "call", operands=(0,), symbol="consume"),
                ),
                MirTerminator("return"),
            ),
        ),
        0,
    )
    abi = MirAbiModule(
        MirModule("unit_call", (caller, consume)),
        (
            MirFunctionSignature("invoke"),
            MirFunctionSignature("consume", (MirParameter("flag", 0, BOOL),)),
        ),
    )
    generated = emit_c_abi_module(abi)
    assert "void consume(bool p0);" in generated
    assert "consume(m0);" in generated
    run = compile_and_run(
        tmp_path,
        abi,
        "int main(void) { invoke(); return 0; }",
    )
    assert run.returncode == 0


def test_exported_name_is_used_for_prototype_definition_and_call(tmp_path):
    add = binary_function("internal_add")
    caller = MirFunction(
        "caller",
        I64,
        (MirLocal(0, "a", I64), MirLocal(1, "b", I64), MirLocal(2, "out", I64)),
        (
            MirBlock(
                0,
                (
                    MirInstruction(0, "const", result=0, value=40),
                    MirInstruction(1, "const", result=1, value=2),
                    MirInstruction(2, "call", result=2, operands=(0, 1), symbol="internal_add"),
                ),
                MirTerminator("return", operands=(2,)),
            ),
        ),
        0,
    )
    abi = MirAbiModule(
        MirModule("exports", (caller, add)),
        (
            MirFunctionSignature("caller"),
            binary_signature("internal_add", "merit_add_i64"),
        ),
    )
    generated = emit_c_abi_module(abi)
    assert "int64_t merit_add_i64(int64_t p0, int64_t p1);" in generated
    assert "m2 = merit_add_i64(m0, m1);" in generated
    run = compile_and_run(
        tmp_path,
        abi,
        "int main(void) { return caller() == 42 ? 0 : 1; }",
    )
    assert run.returncode == 0


@pytest.mark.parametrize(
    "signature,message",
    [
        (MirFunctionSignature("add", (MirParameter("x", 9, I64),)), "unknown local"),
        (MirFunctionSignature("add", (MirParameter("x", 0, BOOL),)), "type does not match"),
        (
            MirFunctionSignature(
                "add",
                (MirParameter("x", 0, I64, ownership="owned"),),
            ),
            "ownership does not match",
        ),
        (
            MirFunctionSignature(
                "add",
                (MirParameter("x", 0, I64, mutable=True),),
            ),
            "mutability does not match",
        ),
    ],
)
def test_parameter_binding_must_match_mir_local(signature, message):
    with pytest.raises(MirAbiError, match=message):
        MirAbiModule(MirModule("math", (binary_function(),)), (signature,))


def test_signature_set_must_exactly_cover_module():
    with pytest.raises(MirAbiError, match="exactly cover"):
        MirAbiModule(MirModule("math", (binary_function(),)), ())


def test_duplicate_parameter_names_and_locals_are_rejected():
    with pytest.raises(MirAbiError, match="duplicate parameter name"):
        MirFunctionSignature(
            "f",
            (MirParameter("x", 0, I64), MirParameter("x", 1, I64)),
        )
    with pytest.raises(MirAbiError, match="duplicate parameter local ID"):
        MirFunctionSignature(
            "f",
            (MirParameter("x", 0, I64), MirParameter("y", 0, I64)),
        )


def test_call_argument_count_must_match():
    add = binary_function()
    caller = MirFunction(
        "bad",
        I64,
        (MirLocal(0, "value", I64), MirLocal(1, "result", I64)),
        (
            MirBlock(
                0,
                (
                    MirInstruction(0, "const", result=0, value=42),
                    MirInstruction(1, "call", result=1, operands=(0,), symbol="add"),
                ),
                MirTerminator("return", operands=(1,)),
            ),
        ),
        0,
    )
    abi = MirAbiModule(
        MirModule("bad", (caller, add)),
        (MirFunctionSignature("bad"), binary_signature()),
    )
    with pytest.raises(MirAbiToCError, match="expects 2 arguments, got 1"):
        emit_c_abi_module(abi)


def test_exported_c_name_collisions_are_rejected():
    first = MirFunction("first", UNIT, (), (MirBlock(0, (), MirTerminator("return")),), 0)
    second = MirFunction("second", UNIT, (), (MirBlock(0, (), MirTerminator("return")),), 0)
    abi = MirAbiModule(
        MirModule("collision", (first, second)),
        (
            MirFunctionSignature("first", exported_name="same-name"),
            MirFunctionSignature("second", exported_name="same_name"),
        ),
    )
    with pytest.raises(MirAbiToCError, match="collide as C identifier"):
        emit_c_abi_module(abi)


def test_parse_rejects_invalid_schema():
    with pytest.raises(MirAbiError, match="expected ABI schema"):
        parse_mir_abi({"schema": "wrong", "module": {}, "signatures": []})
