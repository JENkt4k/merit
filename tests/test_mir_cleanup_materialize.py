import shutil
import subprocess

import pytest

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature, MirParameter
from merit.bootstrap.mir_cleanup_materialize import (
    MirCleanupMaterializationError,
    materialize_cleanup_mir,
)
from merit.bootstrap.mir_cleanup_to_c import CleanupCPolicy, DestructorBinding
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
    canonical_mir_json,
)
from merit.bootstrap.mir_materialized_to_c import emit_c_materialized_cleanup
from merit.bootstrap.mir_ownership import analyze_ownership

I64 = MirType("i64")
BOOL = MirType("bool")
UNIT = MirType("unit")


def local(id_, name, ownership="value", type_=I64):
    return MirLocal(id_, name, type_, ownership=ownership)


def function(name, locals_, blocks, return_type=UNIT):
    return MirFunction(name, return_type, tuple(locals_), tuple(blocks), 0)


def parameter(name, id_, ownership="value", type_=I64):
    return MirParameter(name, id_, type_, ownership)


def signature(name, parameters=()):
    return MirFunctionSignature(name, tuple(parameters))


def abi(functions, signatures):
    return MirAbiModule(MirModule("cleanup_mir", tuple(functions)), tuple(signatures))


def policy():
    return CleanupCPolicy((DestructorBinding(I64, "destroy_i64"),))


def compile_run(tmp_path, generated, main):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler unavailable")
    source = generated + "\nstatic int drops; static int64_t sum;\n" + \
        "void destroy_i64(int64_t v) { drops++; sum += v; }\n" + main
    path = tmp_path / "program.c"
    exe = tmp_path / "program"
    path.write_text(source)
    build = subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(path), "-o", str(exe)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    return subprocess.run([str(exe)], capture_output=True, text=True)


def test_implicit_return_cleanup_becomes_drop_instruction():
    fn = function("discard", [local(0, "x", "owned")], [MirBlock(0, (), MirTerminator("return"))])
    module = abi([fn], [signature("discard", [parameter("x", 0, "owned")])])
    result = materialize_cleanup_mir(module, policy())
    instruction = result.module.functions[0].blocks[0].instructions[0]
    assert (instruction.kind, instruction.operands, instruction.symbol, instruction.ownership) == (
        "drop", (0,), "destroy_i64", "owned"
    )


def test_explicit_drop_receives_typed_destructor_symbol():
    fn = function(
        "discard",
        [local(0, "x", "owned")],
        [MirBlock(0, (MirInstruction(7, "drop", operands=(0,)),), MirTerminator("return"))],
    )
    module = abi([fn], [signature("discard", [parameter("x", 0, "owned")])])
    instruction = materialize_cleanup_mir(module, policy()).module.functions[0].blocks[0].instructions[0]
    assert instruction.instruction_id == 0
    assert instruction.symbol == "destroy_i64"


def test_instruction_ids_are_renumbered_globally_and_deterministically():
    fn = function(
        "f",
        [local(0, "x", "owned"), local(1, "c", type_=BOOL)],
        [
            MirBlock(0, (MirInstruction(20, "nop"),), MirTerminator("branch", operands=(1,), targets=(1, 2))),
            MirBlock(1, (MirInstruction(30, "nop"),), MirTerminator("return")),
            MirBlock(2, (MirInstruction(40, "nop"),), MirTerminator("return")),
        ],
    )
    module = abi([fn], [signature("f", [parameter("x", 0, "owned"), parameter("c", 1, type_=BOOL)])])
    ids = [i.instruction_id for b in materialize_cleanup_mir(module, policy()).module.functions[0].blocks for i in b.instructions]
    assert ids == [0, 1, 2, 3, 4]


def test_owned_return_is_not_materialized_as_cleanup():
    fn = function(
        "identity",
        [local(0, "x", "owned")],
        [MirBlock(0, (), MirTerminator("return", operands=(0,)))],
        I64,
    )
    module = abi([fn], [signature("identity", [parameter("x", 0, "owned")])])
    assert materialize_cleanup_mir(module, CleanupCPolicy(())).module.functions[0].blocks[0].instructions == ()


def test_explicit_and_implicit_cleanup_execute_once(tmp_path):
    explicit = function(
        "explicit",
        [local(0, "x", "owned")],
        [MirBlock(0, (MirInstruction(0, "drop", operands=(0,)),), MirTerminator("return"))],
    )
    implicit = function(
        "implicit",
        [local(0, "x", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
    )
    module = abi(
        [explicit, implicit],
        [
            signature("explicit", [parameter("x", 0, "owned")]),
            signature("implicit", [parameter("x", 0, "owned")]),
        ],
    )
    run = compile_run(
        tmp_path,
        emit_c_materialized_cleanup(module, policy()),
        "int main(void) { explicit(20); implicit(22); return drops == 2 && sum == 42 ? 0 : 1; }",
    )
    assert run.returncode == 0


def test_owned_call_moves_cleanup_to_callee(tmp_path):
    caller = function(
        "caller",
        [local(0, "x", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="consume"),), MirTerminator("return"))],
    )
    consume = function("consume", [local(0, "x", "owned")], [MirBlock(0, (), MirTerminator("return"))])
    module = abi(
        [caller, consume],
        [
            signature("caller", [parameter("x", 0, "owned")]),
            signature("consume", [parameter("x", 0, "owned")]),
        ],
    )
    generated = emit_c_materialized_cleanup(module, policy())
    assert generated.count("destroy_i64(m0);") == 1
    assert compile_run(tmp_path, generated, "int main(void) { caller(42); return drops == 1 && sum == 42 ? 0 : 1; }").returncode == 0


def test_borrowed_call_leaves_cleanup_in_caller(tmp_path):
    caller = function(
        "caller",
        [local(0, "x", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="inspect"),), MirTerminator("return"))],
    )
    inspect = function("inspect", [local(0, "x", "borrowed")], [MirBlock(0, (), MirTerminator("return"))])
    module = abi(
        [caller, inspect],
        [
            signature("caller", [parameter("x", 0, "owned")]),
            signature("inspect", [parameter("x", 0, "borrowed")]),
        ],
    )
    assert compile_run(tmp_path, emit_c_materialized_cleanup(module, policy()), "int main(void) { caller(42); return drops == 1 && sum == 42 ? 0 : 1; }").returncode == 0


def test_each_return_path_contains_explicit_drop(tmp_path):
    fn = function(
        "choose",
        [local(0, "x", "owned"), local(1, "c", type_=BOOL)],
        [
            MirBlock(0, (), MirTerminator("branch", operands=(1,), targets=(1, 2))),
            MirBlock(1, (), MirTerminator("return")),
            MirBlock(2, (), MirTerminator("return")),
        ],
    )
    module = abi([fn], [signature("choose", [parameter("x", 0, "owned"), parameter("c", 1, type_=BOOL)])])
    materialized = materialize_cleanup_mir(module, policy())
    assert [b.instructions[-1].kind for b in materialized.module.functions[0].blocks[1:]] == ["drop", "drop"]
    generated = emit_c_materialized_cleanup(module, policy())
    assert compile_run(tmp_path, generated, "int main(void) { choose(20, true); choose(22, false); return drops == 2 && sum == 42 ? 0 : 1; }").returncode == 0


def test_cleanup_order_is_reverse_local_order():
    fn = function(
        "discard",
        [local(0, "a", "owned"), local(1, "b", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
    )
    module = abi([fn], [signature("discard", [parameter("a", 0, "owned"), parameter("b", 1, "owned")])])
    instructions = materialize_cleanup_mir(module, policy()).module.functions[0].blocks[0].instructions
    assert [instruction.operands[0] for instruction in instructions] == [1, 0]


def test_missing_destructor_fails_closed():
    fn = function("discard", [local(0, "x", "owned")], [MirBlock(0, (), MirTerminator("return"))])
    module = abi([fn], [signature("discard", [parameter("x", 0, "owned")])])
    with pytest.raises(MirCleanupMaterializationError, match="missing destructor"):
        materialize_cleanup_mir(module, CleanupCPolicy(()))


def test_explicit_drop_of_non_owned_local_fails_closed():
    fn = function("bad", [local(0, "x")], [MirBlock(0, (MirInstruction(0, "drop", operands=(0,)),), MirTerminator("return"))])
    module = abi([fn], [signature("bad", [parameter("x", 0)])])
    with pytest.raises(MirCleanupMaterializationError, match="non-owned"):
        materialize_cleanup_mir(module, policy())


def test_stale_plan_fails_closed():
    fn = function("discard", [local(0, "x", "owned")], [MirBlock(0, (), MirTerminator("return"))])
    module = abi([fn], [signature("discard", [parameter("x", 0, "owned")])])
    clean = function("clean", [], [MirBlock(0, (), MirTerminator("return"))])
    stale = analyze_ownership(abi([clean], [signature("clean")]))
    with pytest.raises(MirCleanupMaterializationError, match="stale"):
        materialize_cleanup_mir(module, policy(), ownership_plan=stale)


def test_materialized_mir_is_canonical_and_deterministic():
    fn = function("discard", [local(0, "x", "owned")], [MirBlock(0, (), MirTerminator("return"))])
    module = abi([fn], [signature("discard", [parameter("x", 0, "owned")])])
    first = materialize_cleanup_mir(module, policy())
    second = materialize_cleanup_mir(module, policy())
    assert canonical_mir_json(first.module) == canonical_mir_json(second.module)
    assert emit_c_materialized_cleanup(module, policy()) == emit_c_materialized_cleanup(module, policy())
