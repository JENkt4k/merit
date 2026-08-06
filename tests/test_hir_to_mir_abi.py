import shutil
import subprocess

import pytest

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType
from merit.bootstrap.hir_to_mir_abi import HirToMirAbiError, lower_hir_to_mir_abi
from merit.bootstrap.mir_abi import canonical_mir_abi_json
from merit.bootstrap.mir_abi_to_c import emit_c_abi_module


I64 = HirType("i64")
BOOL = HirType("bool")
UNIT = HirType("unit")


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


def add_module():
    bindings = (
        HirBinding(10, "left", I64),
        HirBinding(20, "right", I64),
    )
    nodes = (
        HirNode(0, "parameter", I64, binding_id=10, ownership="value"),
        HirNode(1, "parameter", I64, binding_id=20, ownership="value"),
        HirNode(2, "identifier", I64, binding_id=10),
        HirNode(3, "identifier", I64, binding_id=20),
        HirNode(4, "binary", I64, (2, 3), symbol="+", numeric_policy="checked"),
        HirNode(5, "return", UNIT, (4,)),
        HirNode(6, "function", I64, (0, 1, 5), symbol="add"),
    )
    return HirModule("add", bindings, nodes, (6,))


def test_derives_ordered_parameters_and_native_addition(tmp_path):
    abi = lower_hir_to_mir_abi(add_module())
    signature = abi.signatures[0]
    assert signature.function == "add"
    assert [parameter.name for parameter in signature.parameters] == ["left", "right"]
    assert [parameter.local_id for parameter in signature.parameters] == [0, 1]
    assert [parameter.type.name for parameter in signature.parameters] == ["i64", "i64"]
    generated = emit_c_abi_module(abi)
    assert "int64_t add(int64_t p0, int64_t p1);" in generated
    assert generated.index("int64_t m0 = p0") < generated.index("int64_t m1 = p1")
    run = compile_and_run(tmp_path, abi, "int main(void) { return add(20, 22) == 42 ? 0 : 1; }")
    assert run.returncode == 0


def test_parameter_order_is_source_order_not_binding_id_order(tmp_path):
    bindings = (
        HirBinding(10, "right", I64),
        HirBinding(90, "left", I64),
    )
    nodes = (
        HirNode(0, "parameter", I64, binding_id=90, ownership="value"),
        HirNode(1, "parameter", I64, binding_id=10, ownership="value"),
        HirNode(2, "identifier", I64, binding_id=90),
        HirNode(3, "identifier", I64, binding_id=10),
        HirNode(4, "binary", I64, (2, 3), symbol="-", numeric_policy="checked"),
        HirNode(5, "return", UNIT, (4,)),
        HirNode(6, "function", I64, (0, 1, 5), symbol="subtract"),
    )
    abi = lower_hir_to_mir_abi(HirModule("order", bindings, nodes, (6,)))
    signature = abi.signatures[0]
    assert [parameter.name for parameter in signature.parameters] == ["left", "right"]
    assert [parameter.local_id for parameter in signature.parameters] == [1, 0]
    run = compile_and_run(tmp_path, abi, "int main(void) { return subtract(50, 8) == 42 ? 0 : 1; }")
    assert run.returncode == 0


def caller_module():
    bindings = (
        HirBinding(0, "left", I64),
        HirBinding(1, "right", I64),
    )
    nodes = (
        HirNode(0, "parameter", I64, binding_id=0, ownership="value"),
        HirNode(1, "parameter", I64, binding_id=1, ownership="value"),
        HirNode(2, "identifier", I64, binding_id=0),
        HirNode(3, "identifier", I64, binding_id=1),
        HirNode(4, "binary", I64, (2, 3), symbol="+", numeric_policy="checked"),
        HirNode(5, "return", UNIT, (4,)),
        HirNode(6, "function", I64, (0, 1, 5), symbol="add"),
        HirNode(7, "literal", I64, value=20),
        HirNode(8, "literal", I64, value=22),
        HirNode(9, "call", I64, (7, 8), symbol="add"),
        HirNode(10, "return", UNIT, (9,)),
        HirNode(11, "function", I64, (10,), symbol="answer"),
    )
    return HirModule("calls", bindings, nodes, (11, 6))


def test_hir_call_operands_flow_through_mir_abi_and_native_code(tmp_path):
    abi = lower_hir_to_mir_abi(caller_module())
    assert [signature.function for signature in abi.signatures] == ["answer", "add"]
    answer = abi.module.functions[0]
    calls = [
        instruction
        for block in answer.blocks
        for instruction in block.instructions
        if instruction.kind == "call"
    ]
    assert len(calls) == 1
    assert calls[0].symbol == "add"
    assert len(calls[0].operands) == 2
    generated = emit_c_abi_module(abi)
    assert "m4 = add(m2, m3);" in generated
    run = compile_and_run(tmp_path, abi, "int main(void) { return answer() == 42 ? 0 : 1; }")
    assert run.returncode == 0


def test_export_policy_is_explicit_and_applied_to_calls(tmp_path):
    abi = lower_hir_to_mir_abi(caller_module(), exported_names={"add": "merit_add_i64"})
    generated = emit_c_abi_module(abi)
    assert "int64_t merit_add_i64(int64_t p0, int64_t p1);" in generated
    assert "merit_add_i64(m2, m3)" in generated
    run = compile_and_run(tmp_path, abi, "int main(void) { return answer() == 42 ? 0 : 1; }")
    assert run.returncode == 0


def test_canonical_abi_is_deterministic():
    first = lower_hir_to_mir_abi(caller_module(), exported_names={"add": "merit_add_i64"})
    second = lower_hir_to_mir_abi(caller_module(), exported_names={"add": "merit_add_i64"})
    assert canonical_mir_abi_json(first) == canonical_mir_abi_json(second)


def test_bool_parameter_is_derived():
    bindings = (HirBinding(4, "flag", BOOL),)
    nodes = (
        HirNode(0, "parameter", BOOL, binding_id=4, ownership="value"),
        HirNode(1, "identifier", BOOL, binding_id=4),
        HirNode(2, "return", UNIT, (1,)),
        HirNode(3, "function", BOOL, (0, 2), symbol="identity"),
    )
    abi = lower_hir_to_mir_abi(HirModule("bool", bindings, nodes, (3,)))
    parameter = abi.signatures[0].parameters[0]
    assert parameter.type.name == "bool"
    assert parameter.local_id == 0


def test_owned_parameter_metadata_is_preserved():
    box = HirType("i64")
    bindings = (HirBinding(3, "item", box, ownership="owned"),)
    nodes = (
        HirNode(0, "parameter", box, binding_id=3, ownership="owned"),
        HirNode(1, "identifier", box, binding_id=3, ownership="owned"),
        HirNode(2, "return", UNIT, (1,)),
        HirNode(3, "function", box, (0, 2), symbol="identity_owned"),
    )
    abi = lower_hir_to_mir_abi(HirModule("owned", bindings, nodes, (3,)))
    assert abi.signatures[0].parameters[0].ownership == "owned"
    assert abi.module.functions[0].locals[0].ownership == "owned"


@pytest.mark.parametrize(
    "module,message",
    [
        (
            HirModule(
                "late",
                (HirBinding(0, "x", I64),),
                (
                    HirNode(0, "literal", I64, value=1),
                    HirNode(1, "parameter", I64, binding_id=0, ownership="value"),
                    HirNode(2, "return", UNIT, (0,)),
                    HirNode(3, "function", I64, (0, 1, 2), symbol="late"),
                ),
                (3,),
            ),
            "parameter after executable",
        ),
        (
            HirModule(
                "child",
                (HirBinding(0, "x", I64),),
                (
                    HirNode(0, "literal", I64, value=1),
                    HirNode(1, "parameter", I64, (0,), binding_id=0, ownership="value"),
                    HirNode(2, "return", UNIT, (0,)),
                    HirNode(3, "function", I64, (1, 2), symbol="child"),
                ),
                (3,),
            ),
            "cannot have children",
        ),
        (
            HirModule(
                "type",
                (HirBinding(0, "x", I64),),
                (
                    HirNode(0, "parameter", BOOL, binding_id=0, ownership="value"),
                    HirNode(1, "literal", I64, value=1),
                    HirNode(2, "return", UNIT, (1,)),
                    HirNode(3, "function", I64, (0, 2), symbol="bad"),
                ),
                (3,),
            ),
            "type does not match",
        ),
        (
            HirModule(
                "ownership",
                (HirBinding(0, "x", I64, ownership="owned"),),
                (
                    HirNode(0, "parameter", I64, binding_id=0, ownership="value"),
                    HirNode(1, "identifier", I64, binding_id=0),
                    HirNode(2, "return", UNIT, (1,)),
                    HirNode(3, "function", I64, (0, 2), symbol="bad"),
                ),
                (3,),
            ),
            "ownership does not match",
        ),
    ],
)
def test_invalid_parameter_declarations_fail_closed(module, message):
    with pytest.raises(HirToMirAbiError, match=message):
        lower_hir_to_mir_abi(module)


def test_duplicate_parameter_binding_fails_closed():
    bindings = (HirBinding(0, "x", I64),)
    nodes = (
        HirNode(0, "parameter", I64, binding_id=0, ownership="value"),
        HirNode(1, "parameter", I64, binding_id=0, ownership="value"),
        HirNode(2, "identifier", I64, binding_id=0),
        HirNode(3, "return", UNIT, (2,)),
        HirNode(4, "function", I64, (0, 1, 3), symbol="bad"),
    )
    with pytest.raises(HirToMirAbiError, match="repeats a parameter binding"):
        lower_hir_to_mir_abi(HirModule("duplicate", bindings, nodes, (4,)))


def test_unknown_export_policy_function_fails_closed():
    with pytest.raises(HirToMirAbiError, match="unknown functions"):
        lower_hir_to_mir_abi(add_module(), exported_names={"missing": "missing_export"})


def test_unknown_call_target_fails_closed():
    nodes = (
        HirNode(0, "call", I64, symbol="missing"),
        HirNode(1, "return", UNIT, (0,)),
        HirNode(2, "function", I64, (1,), symbol="caller"),
    )
    with pytest.raises(HirToMirAbiError, match="unknown HIR function"):
        lower_hir_to_mir_abi(HirModule("unknown", (), nodes, (2,)))


def test_call_arity_mismatch_fails_closed():
    module = caller_module()
    nodes = tuple(
        HirNode(node.node_id, node.kind, node.type, (7,) if node.node_id == 9 else node.children,
                node.span, node.binding_id, node.symbol, node.value, node.ownership,
                node.numeric_policy, node.conversion_policy, node.capabilities)
        for node in module.nodes
    )
    with pytest.raises(HirToMirAbiError, match="expects 2 arguments, got 1"):
        lower_hir_to_mir_abi(HirModule(module.name, module.bindings, nodes, module.roots))


def test_call_type_mismatch_fails_closed():
    module = caller_module()
    nodes = tuple(
        HirNode(node.node_id, node.kind, BOOL if node.node_id == 8 else node.type, node.children,
                node.span, node.binding_id, node.symbol,
                True if node.node_id == 8 else node.value, node.ownership,
                node.numeric_policy, node.conversion_policy, node.capabilities)
        for node in module.nodes
    )
    with pytest.raises(HirToMirAbiError, match="argument 1 type"):
        lower_hir_to_mir_abi(HirModule(module.name, module.bindings, nodes, module.roots))


def test_owned_call_requires_transfer_semantics():
    bindings = (HirBinding(0, "item", I64, ownership="owned"),)
    nodes = (
        HirNode(0, "parameter", I64, binding_id=0, ownership="owned"),
        HirNode(1, "identifier", I64, binding_id=0, ownership="owned"),
        HirNode(2, "return", UNIT, (1,)),
        HirNode(3, "function", I64, (0, 2), symbol="consume"),
        HirNode(4, "literal", I64, value=1, ownership="value"),
        HirNode(5, "call", I64, (4,), symbol="consume"),
        HirNode(6, "return", UNIT, (5,)),
        HirNode(7, "function", I64, (6,), symbol="caller"),
    )
    with pytest.raises(HirToMirAbiError, match="must transfer an owned value"):
        lower_hir_to_mir_abi(HirModule("owned_call", bindings, nodes, (3, 7)))
