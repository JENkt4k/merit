import shutil
import subprocess

import pytest

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature, MirParameter
from merit.bootstrap.mir_cleanup_to_c import (
    CleanupCPolicy,
    DestructorBinding,
    MirCleanupToCError,
    canonical_cleanup_policy_json,
    emit_c_abi_module_with_cleanup,
)
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
)
from merit.bootstrap.mir_ownership import OwnershipPlan, analyze_ownership

I64 = MirType("i64")
UNIT = MirType("unit")
BOOL = MirType("bool")


def local(local_id, name, ownership="value", type_=I64):
    return MirLocal(local_id, name, type_, ownership=ownership)


def function(name, locals_, blocks, return_type=I64):
    return MirFunction(name, return_type, tuple(locals_), tuple(blocks), 0)


def signature(name, parameters=(), exported_name=None):
    return MirFunctionSignature(name, tuple(parameters), exported_name)


def parameter(name, local_id, ownership="value", type_=I64):
    return MirParameter(name, local_id, type_, ownership)


def abi(functions, signatures):
    return MirAbiModule(MirModule("cleanup", tuple(functions)), tuple(signatures))


def policy(*bindings):
    return CleanupCPolicy(tuple(bindings))


def compile_and_run(tmp_path, generated, support):
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler unavailable")
    source = generated + "\n" + support
    path = tmp_path / "program.c"
    executable = tmp_path / "program"
    path.write_text(source)
    build = subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(path), "-o", str(executable)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    return subprocess.run([str(executable)], capture_output=True, text=True)


def counter_support(main):
    return f"""
static int drop_count = 0;
static int64_t drop_sum = 0;
void destroy_i64(int64_t value) {{ drop_count += 1; drop_sum += value; }}
{main}
"""


def test_implicit_owned_parameter_cleanup_executes_once(tmp_path):
    discard = function(
        "discard",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    module = abi([discard], [signature("discard", [parameter("item", 0, "owned")])])
    generated = emit_c_abi_module_with_cleanup(
        module, policy(DestructorBinding(I64, "destroy_i64"))
    )
    assert generated.count("destroy_i64(m0);") == 1
    run = compile_and_run(
        tmp_path,
        generated,
        counter_support(
            "int main(void) { discard(42); return drop_count == 1 && drop_sum == 42 ? 0 : 1; }"
        ),
    )
    assert run.returncode == 0


def test_two_owned_values_cleanup_in_reverse_local_order(tmp_path):
    discard = function(
        "discard_two",
        [local(0, "first", "owned"), local(1, "second", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    module = abi(
        [discard],
        [signature("discard_two", [parameter("first", 0, "owned"), parameter("second", 1, "owned")])],
    )
    generated = emit_c_abi_module_with_cleanup(
        module, policy(DestructorBinding(I64, "destroy_i64"))
    )
    assert generated.index("destroy_i64(m1);") < generated.index("destroy_i64(m0);")
    run = compile_and_run(
        tmp_path,
        generated,
        counter_support(
            "int main(void) { discard_two(20, 22); return drop_count == 2 && drop_sum == 42 ? 0 : 1; }"
        ),
    )
    assert run.returncode == 0


def test_owned_return_transfers_without_cleanup(tmp_path):
    identity = function(
        "identity",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return", operands=(0,)))],
    )
    module = abi([identity], [signature("identity", [parameter("item", 0, "owned")])])
    generated = emit_c_abi_module_with_cleanup(module, policy())
    assert "destroy_i64" not in generated
    run = compile_and_run(
        tmp_path,
        generated,
        "int main(void) { return identity(42) == 42 ? 0 : 1; }",
    )
    assert run.returncode == 0


def test_owned_call_moves_to_callee_and_destroys_once(tmp_path):
    consume = function(
        "consume",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    caller = function(
        "caller",
        [local(0, "item", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="consume"),), MirTerminator("return"))],
        UNIT,
    )
    module = abi(
        [caller, consume],
        [
            signature("caller", [parameter("item", 0, "owned")]),
            signature("consume", [parameter("item", 0, "owned")]),
        ],
    )
    generated = emit_c_abi_module_with_cleanup(
        module, policy(DestructorBinding(I64, "destroy_i64"))
    )
    assert generated.count("destroy_i64(m0);") == 1
    run = compile_and_run(
        tmp_path,
        generated,
        counter_support(
            "int main(void) { caller(42); return drop_count == 1 && drop_sum == 42 ? 0 : 1; }"
        ),
    )
    assert run.returncode == 0


def test_borrowed_call_retains_caller_cleanup(tmp_path):
    inspect = function(
        "inspect",
        [local(0, "item", "borrowed")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    caller = function(
        "caller",
        [local(0, "item", "owned")],
        [MirBlock(0, (MirInstruction(0, "call", operands=(0,), symbol="inspect"),), MirTerminator("return"))],
        UNIT,
    )
    module = abi(
        [caller, inspect],
        [
            signature("caller", [parameter("item", 0, "owned")]),
            signature("inspect", [parameter("item", 0, "borrowed")]),
        ],
    )
    generated = emit_c_abi_module_with_cleanup(
        module, policy(DestructorBinding(I64, "destroy_i64"))
    )
    run = compile_and_run(
        tmp_path,
        generated,
        counter_support(
            "int main(void) { caller(42); return drop_count == 1 && drop_sum == 42 ? 0 : 1; }"
        ),
    )
    assert run.returncode == 0


def test_each_return_edge_materializes_independent_cleanup(tmp_path):
    choose = function(
        "choose",
        [local(0, "item", "owned"), local(1, "condition", type_=BOOL)],
        [
            MirBlock(0, (), MirTerminator("branch", operands=(1,), targets=(1, 2))),
            MirBlock(1, (), MirTerminator("return")),
            MirBlock(2, (), MirTerminator("return")),
        ],
        UNIT,
    )
    module = abi(
        [choose],
        [signature("choose", [parameter("item", 0, "owned"), parameter("condition", 1, type_=BOOL)])],
    )
    generated = emit_c_abi_module_with_cleanup(
        module, policy(DestructorBinding(I64, "destroy_i64"))
    )
    assert generated.count("destroy_i64(m0);") == 2
    run = compile_and_run(
        tmp_path,
        generated,
        counter_support(
            "int main(void) { choose(20, true); choose(22, false); return drop_count == 2 && drop_sum == 42 ? 0 : 1; }"
        ),
    )
    assert run.returncode == 0


def test_missing_destructor_binding_fails_closed():
    discard = function(
        "discard",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    module = abi([discard], [signature("discard", [parameter("item", 0, "owned")])])
    with pytest.raises(MirCleanupToCError, match="missing destructor bindings"):
        emit_c_abi_module_with_cleanup(module, policy())


def test_destructor_function_collision_fails_closed():
    destroy = function(
        "destroy_i64",
        [],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    with pytest.raises(MirCleanupToCError, match="collides with an emitted function"):
        emit_c_abi_module_with_cleanup(
            abi([destroy], [signature("destroy_i64")]),
            policy(DestructorBinding(I64, "destroy_i64")),
        )


def test_invalid_destructor_identifier_fails_closed():
    with pytest.raises(MirCleanupToCError, match="valid C identifier"):
        DestructorBinding(I64, "destroy-i64")


def test_duplicate_type_binding_fails_closed():
    with pytest.raises(MirCleanupToCError, match="duplicate destructor type binding"):
        policy(DestructorBinding(I64, "drop_a"), DestructorBinding(I64, "drop_b"))


def test_duplicate_destructor_symbol_fails_closed():
    with pytest.raises(MirCleanupToCError, match="duplicate destructor symbol"):
        policy(DestructorBinding(I64, "drop_value"), DestructorBinding(BOOL, "drop_value"))


def test_supplied_plan_must_match_module_order():
    first = function("first", [], [MirBlock(0, (), MirTerminator("return"))], UNIT)
    second = function("second", [], [MirBlock(0, (), MirTerminator("return"))], UNIT)
    module = abi([first, second], [signature("first"), signature("second")])
    reverse_module = abi([second, first], [signature("second"), signature("first")])
    reverse_plan = analyze_ownership(reverse_module)
    with pytest.raises(MirCleanupToCError, match="exactly match MIR module order"):
        emit_c_abi_module_with_cleanup(module, policy(), ownership_plan=reverse_plan)


def test_cleanup_policy_serialization_is_deterministic():
    value = policy(DestructorBinding(I64, "destroy_i64"), DestructorBinding(BOOL, "destroy_bool"))
    assert canonical_cleanup_policy_json(value) == canonical_cleanup_policy_json(value)
    assert canonical_cleanup_policy_json(value).startswith('{"destructors"')


def test_generated_output_is_deterministic():
    discard = function(
        "discard",
        [local(0, "item", "owned")],
        [MirBlock(0, (), MirTerminator("return"))],
        UNIT,
    )
    module = abi([discard], [signature("discard", [parameter("item", 0, "owned")])])
    cleanup_policy = policy(DestructorBinding(I64, "destroy_i64"))
    assert emit_c_abi_module_with_cleanup(module, cleanup_policy) == emit_c_abi_module_with_cleanup(module, cleanup_policy)


def test_existing_ownership_errors_are_not_bypassed():
    bad = function(
        "bad",
        [local(0, "item", "owned"), local(1, "moved", "owned")],
        [MirBlock(0, (
            MirInstruction(0, "move", result=1, operands=(0,)),
            MirInstruction(1, "borrow", result=0, operands=(0,)),
        ), MirTerminator("return"))],
        UNIT,
    )
    module = abi([bad], [signature("bad", [parameter("item", 0, "owned")])])
    with pytest.raises(Exception, match="non-live owned local"):
        emit_c_abi_module_with_cleanup(module, policy(DestructorBinding(I64, "destroy_i64")))
