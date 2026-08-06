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
    bindings = (HirBinding(10, "left", I64), HirBinding(20, "right", I64))
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


def caller_module():
    bindings = (HirBinding(0, "left", I64), HirBinding(1, "right", I64))
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


def replace_node(module, target_id, **changes):
    nodes = []
    for node in module.nodes:
        if node.node_id != target_id:
            nodes.append(node)
            continue
        values = {
            "node_id": node.node_id,
            "kind": node.kind,
            "type": node.type,
            "children": node.children,
            "span": node.span,
            "binding_id": node.binding_id,
            "symbol": node.symbol,
            "value": node.value,
            "ownership": node.ownership,
            "numeric_policy": node.numeric_policy,
            "conversion_policy": node.conversion_policy,
            "capabilities": node.capabilities,
        }
        values.update(changes)
        nodes.append(HirNode(**values))
    return HirModule(module.name, module.bindings, tuple(nodes), module.roots)


def test_derives_ordered_parameters_and_native_addition(tmp_path):
    abi = lower_hir_to_mir_abi(add_module())
    signature = abi.signatures[0]
    assert signature.function == "add"
    assert [p.name for p in signature.parameters] == ["left", "right"]
    assert [p.local_id for p in signature.parameters] == [0, 1]
    generated = emit_c_abi_module(abi)
    assert "int64_t add(int64_t p0, int64_t p1);" in generated
    assert generated.index("int64_t m0 = p0") < generated.index("int64_t m1 = p1")
    assert compile_and_run(tmp_path, abi, "int main(void) { return add(20, 22) == 42 ? 0 : 1; }").returncode == 0


def test_parameter_source_order_is_independent_of_binding_id_order(tmp_path):
    bindings = (HirBinding(10, "right", I64), HirBinding(90, "left", I64))
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
    assert [p.name for p in abi.signatures[0].parameters] == ["left", "right"]
    assert [p.local_id for p in abi.signatures[0].parameters] == [1, 0]
    assert compile_and_run(tmp_path, abi, "int main(void) { return subtract(50, 8) == 42 ? 0 : 1; }").returncode == 0


def test_hir_calls_flow_through_mir_abi_and_native_code(tmp_path):
    abi = lower_hir_to_mir_abi(caller_module())
    answer = abi.module.functions[0]
    call = next(i for b in answer.blocks for i in b.instructions if i.kind == "call")
    assert call.symbol == "add"
    assert len(call.operands) == 2
    generated = emit_c_abi_module(abi)
    expected = f"m{call.result} = add(" + ", ".join(f"m{x}" for x in call.operands) + ");"
    assert expected in generated
    assert compile_and_run(tmp_path, abi, "int main(void) { return answer() == 42 ? 0 : 1; }").returncode == 0


def test_explicit_export_policy_applies_to_definition_and_calls(tmp_path):
    abi = lower_hir_to_mir_abi(caller_module(), exported_names={"add": "merit_add_i64"})
    answer = abi.module.functions[0]
    call = next(i for b in answer.blocks for i in b.instructions if i.kind == "call")
    generated = emit_c_abi_module(abi)
    assert "int64_t merit_add_i64(int64_t p0, int64_t p1);" in generated
    expected = "merit_add_i64(" + ", ".join(f"m{x}" for x in call.operands) + ")"
    assert expected in generated
    assert compile_and_run(tmp_path, abi, "int main(void) { return answer() == 42 ? 0 : 1; }").returncode == 0


def test_canonical_abi_is_deterministic():
    first = lower_hir_to_mir_abi(caller_module(), exported_names={"add": "merit_add_i64"})
    second = lower_hir_to_mir_abi(caller_module(), exported_names={"add": "merit_add_i64"})
    assert canonical_mir_abi_json(first) == canonical_mir_abi_json(second)


def test_bool_and_owned_parameter_metadata_are_derived():
    bool_module = HirModule(
        "bool",
        (HirBinding(4, "flag", BOOL),),
        (
            HirNode(0, "parameter", BOOL, binding_id=4, ownership="value"),
            HirNode(1, "identifier", BOOL, binding_id=4),
            HirNode(2, "return", UNIT, (1,)),
            HirNode(3, "function", BOOL, (0, 2), symbol="identity"),
        ),
        (3,),
    )
    assert lower_hir_to_mir_abi(bool_module).signatures[0].parameters[0].type.name == "bool"

    owned_module = HirModule(
        "owned",
        (HirBinding(3, "item", I64, ownership="owned"),),
        (
            HirNode(0, "parameter", I64, binding_id=3, ownership="owned"),
            HirNode(1, "identifier", I64, binding_id=3, ownership="owned"),
            HirNode(2, "return", UNIT, (1,)),
            HirNode(3, "function", I64, (0, 2), symbol="identity_owned"),
        ),
        (3,),
    )
    abi = lower_hir_to_mir_abi(owned_module)
    assert abi.signatures[0].parameters[0].ownership == "owned"
    assert abi.module.functions[0].locals[0].ownership == "owned"


def invalid_parameter_module(kind):
    binding = HirBinding(0, "x", I64, ownership="owned" if kind == "ownership" else "value")
    parameter_type = BOOL if kind == "type" else I64
    ownership = "value"
    children = (0,) if kind == "children" else ()
    parameter = HirNode(1, "parameter", parameter_type, children, binding_id=0, ownership=ownership)
    literal = HirNode(0, "literal", I64, value=1)
    ret = HirNode(2, "return", UNIT, (0,))
    function_children = (0, 1, 2) if kind == "late" else (1, 2)
    function = HirNode(3, "function", I64, function_children, symbol="bad")
    return HirModule(kind, (binding,), (literal, parameter, ret, function), (3,))


@pytest.mark.parametrize(
    "kind,message",
    [
        ("late", "parameter after executable"),
        ("children", "cannot have children"),
        ("type", "type does not match"),
        ("ownership", "ownership does not match"),
    ],
)
def test_invalid_parameter_declarations_fail_closed(kind, message):
    with pytest.raises(HirToMirAbiError, match=message):
        lower_hir_to_mir_abi(invalid_parameter_module(kind))


def test_duplicate_parameter_binding_fails_closed():
    module = HirModule(
        "duplicate",
        (HirBinding(0, "x", I64),),
        (
            HirNode(0, "parameter", I64, binding_id=0, ownership="value"),
            HirNode(1, "parameter", I64, binding_id=0, ownership="value"),
            HirNode(2, "identifier", I64, binding_id=0),
            HirNode(3, "return", UNIT, (2,)),
            HirNode(4, "function", I64, (0, 1, 3), symbol="bad"),
        ),
        (4,),
    )
    with pytest.raises(HirToMirAbiError, match="repeats a parameter binding"):
        lower_hir_to_mir_abi(module)


def test_unknown_export_and_call_targets_fail_closed():
    with pytest.raises(HirToMirAbiError, match="unknown functions"):
        lower_hir_to_mir_abi(add_module(), exported_names={"missing": "missing_export"})

    unknown = HirModule(
        "unknown",
        (),
        (
            HirNode(0, "call", I64, symbol="missing"),
            HirNode(1, "return", UNIT, (0,)),
            HirNode(2, "function", I64, (1,), symbol="caller"),
        ),
        (2,),
    )
    with pytest.raises(HirToMirAbiError, match="unknown HIR function"):
        lower_hir_to_mir_abi(unknown)


def test_call_arity_and_type_mismatches_fail_closed():
    with pytest.raises(HirToMirAbiError, match="expects 2 arguments, got 1"):
        lower_hir_to_mir_abi(replace_node(caller_module(), 9, children=(7,)))
    with pytest.raises(HirToMirAbiError, match="argument 1 type"):
        lower_hir_to_mir_abi(replace_node(caller_module(), 8, type=BOOL, value=True))


def test_owned_call_requires_transfer_semantics():
    module = HirModule(
        "owned_call",
        (HirBinding(0, "item", I64, ownership="owned"),),
        (
            HirNode(0, "parameter", I64, binding_id=0, ownership="owned"),
            HirNode(1, "identifier", I64, binding_id=0, ownership="owned"),
            HirNode(2, "return", UNIT, (1,)),
            HirNode(3, "function", I64, (0, 2), symbol="consume"),
            HirNode(4, "literal", I64, value=1, ownership="value"),
            HirNode(5, "call", I64, (4,), symbol="consume"),
            HirNode(6, "return", UNIT, (5,)),
            HirNode(7, "function", I64, (6,), symbol="caller"),
        ),
        (3, 7),
    )
    with pytest.raises(HirToMirAbiError, match="must transfer an owned value"):
        lower_hir_to_mir_abi(module)
