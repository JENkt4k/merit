import hashlib
import json

import pytest

from merit.bootstrap.hir_contract import (
    HIR_SCHEMA,
    LOCAL_LOAN_HIR_SCHEMA,
    HirBinding,
    HirContractError,
    HirLocalLoan,
    HirModule,
    HirNode,
    HirType,
    SourceSpan,
    canonical_hir_json,
    load_hir_json,
    parse_hir,
)

I32 = HirType("i32")
BOOL = HirType("bool")
MONEY = HirType("Decimal", (HirType("18"), HirType("2")))


def sample_module() -> HirModule:
    bindings = (
        HirBinding(0, "amount", MONEY, ownership="value", span=SourceSpan(3, 6)),
        HirBinding(1, "result", MONEY, mutable=True, ownership="owned"),
    )
    nodes = (
        HirNode(0, "identifier", MONEY, binding_id=0, ownership="value", span=SourceSpan(20, 6)),
        HirNode(1, "literal", MONEY, value="1.25", numeric_policy="exact", span=SourceSpan(29, 4)),
        HirNode(2, "binary", MONEY, children=(0, 1), symbol="+", numeric_policy="exact"),
        HirNode(3, "conversion", MONEY, children=(2,), conversion_policy="checked"),
        HirNode(4, "let", MONEY, children=(3,), binding_id=1, ownership="owned"),
        HirNode(5, "identifier", MONEY, binding_id=1, ownership="borrowed"),
        HirNode(6, "return", MONEY, children=(5,), ownership="owned"),
        HirNode(7, "block", MONEY, children=(4, 6)),
        HirNode(8, "function", MONEY, children=(7,), symbol="credit", capabilities=("allocate",)),
    )
    return HirModule("ledger", bindings, nodes, (8,))


def local_loan_module() -> HirModule:
    bindings = (HirBinding(0, "owner", I32), HirBinding(1, "view", I32, ownership="local_reference"))
    nodes = (HirNode(0, "identifier", I32, binding_id=0),)
    return HirModule("loan", bindings, nodes, (0,), LOCAL_LOAN_HIR_SCHEMA,
                     (HirLocalLoan(1, 0, SourceSpan(4, 17)),))


def test_v2_local_loan_round_trip_keeps_v1_bytes_unchanged():
    old = canonical_hir_json(sample_module())
    module = local_loan_module()
    assert load_hir_json(canonical_hir_json(module)) == module
    assert canonical_hir_json(sample_module()) == old
    with pytest.raises(HirContractError, match="unsupported HIR schema"):
        parse_hir({**module.to_data(), "schema": "bootstrap-hir-v3"})


@pytest.mark.parametrize("change", [
    lambda data: data.update(extra=1),
    lambda data: data["local_loans"][0].update(extra=1),
    lambda data: data["local_loans"][0].update(origin_binding_id=99),
    lambda data: data["local_loans"][0].update(permission="exclusive_write"),
    lambda data: data["local_loans"].append(dict(data["local_loans"][0])),
    lambda data: data["local_loans"][0].update(span=[-1, 3]),
    lambda data: data["local_loans"][0].update(span=[4, 0]),
    lambda data: data["bindings"][0].update(extra=1),
    lambda data: data["bindings"][0]["type"].update(extra=1),
    lambda data: data["nodes"][0].update(extra=1),
    lambda data: data["bindings"][0].update(ownership="local_reference"),
])
def test_v2_rejects_malformed_local_loan_semantics(change):
    data = local_loan_module().to_data()
    change(data)
    with pytest.raises(HirContractError):
        parse_hir(data)


def test_v1_rejects_unversioned_local_loan_record():
    data = sample_module().to_data()
    data["local_loans"] = [HirLocalLoan(1, 0, SourceSpan(1, 3)).to_data()]
    with pytest.raises(HirContractError, match="HIR v1 cannot contain"):
        parse_hir(data)


def test_v1_rejects_v2_print_node() -> None:
    data = sample_module().to_data()
    data["nodes"][0]["kind"] = "print"
    with pytest.raises(HirContractError, match="HIR v1 cannot contain RM1 print"):
        parse_hir(data)


def test_hir_round_trips_canonically():
    module = sample_module()
    encoded = canonical_hir_json(module)
    decoded = load_hir_json(encoded)
    assert decoded == module
    assert canonical_hir_json(decoded) == encoded
    assert json.loads(encoded)["schema"] == HIR_SCHEMA
    assert hashlib.sha256(encoded.encode()).hexdigest() == "467e4a817bb0c966c054083f6aa52b542c1cb63f7743c58ba970db03b94e09ff"


def test_canonical_hir_is_independent_of_mapping_order():
    data = sample_module().to_data()
    reordered = {
        "roots": data["roots"],
        "nodes": data["nodes"],
        "bindings": data["bindings"],
        "name": data["name"],
        "schema": data["schema"],
    }
    assert canonical_hir_json(parse_hir(reordered)) == canonical_hir_json(sample_module())


def test_generic_types_round_trip():
    type_ = HirType("Result", (MONEY, HirType("LedgerError")))
    module = HirModule("types", (), (HirNode(0, "literal", type_, value="ok"),), (0,))
    assert load_hir_json(canonical_hir_json(module)).nodes[0].type == type_


@pytest.mark.parametrize("start,length", [(-1, 0), (0, -1)])
def test_invalid_spans_are_rejected(start, length):
    with pytest.raises(HirContractError, match="non-negative"):
        SourceSpan(start, length)


@pytest.mark.parametrize("ownership", ["unsafe", "shared", "copyish"])
def test_unknown_ownership_modes_are_rejected(ownership):
    with pytest.raises(HirContractError, match="unknown ownership mode"):
        HirBinding(0, "value", I32, ownership=ownership)


@pytest.mark.parametrize("policy", ["implicit", "lossy", "platform"])
def test_unknown_numeric_policies_are_rejected(policy):
    with pytest.raises(HirContractError, match="unknown numeric policy"):
        HirNode(0, "literal", I32, numeric_policy=policy)


def test_duplicate_binding_ids_are_rejected():
    bindings = (HirBinding(0, "a", I32), HirBinding(0, "b", I32))
    with pytest.raises(HirContractError, match="duplicate HIR binding ID"):
        HirModule("bad", bindings, (), ())


def test_duplicate_node_ids_are_rejected():
    nodes = (HirNode(0, "literal", I32, value=1), HirNode(0, "literal", I32, value=2))
    with pytest.raises(HirContractError, match="duplicate HIR node ID"):
        HirModule("bad", (), nodes, (0,))


def test_unknown_roots_are_rejected():
    with pytest.raises(HirContractError, match="unknown root node ID"):
        HirModule("bad", (), (HirNode(0, "literal", I32, value=1),), (7,))


def test_unknown_children_are_rejected():
    with pytest.raises(HirContractError, match="unknown child"):
        HirModule("bad", (), (HirNode(0, "return", I32, children=(4,)),), (0,))


def test_forward_child_references_are_rejected():
    nodes = (
        HirNode(0, "return", I32, children=(1,)),
        HirNode(1, "literal", I32, value=1),
    )
    with pytest.raises(HirContractError, match="postorder"):
        HirModule("bad", (), nodes, (0,))


def test_unknown_binding_references_are_rejected():
    node = HirNode(0, "identifier", I32, binding_id=3)
    with pytest.raises(HirContractError, match="unknown binding"):
        HirModule("bad", (), (node,), (0,))


@pytest.mark.parametrize("kind", ["identifier", "let", "assign", "parameter", "move", "borrow", "drop"])
def test_binding_sensitive_nodes_require_binding_ids(kind):
    with pytest.raises(HirContractError, match="requires a binding ID"):
        HirModule("bad", (), (HirNode(0, kind, I32),), (0,))


def test_binary_nodes_require_explicit_numeric_policy():
    nodes = (
        HirNode(0, "literal", I32, value=1),
        HirNode(1, "literal", I32, value=2),
        HirNode(2, "binary", I32, children=(0, 1), symbol="+"),
    )
    with pytest.raises(HirContractError, match="explicit numeric policy"):
        HirModule("bad", (), nodes, (2,))


def test_conversion_nodes_require_explicit_policy():
    nodes = (
        HirNode(0, "literal", I32, value=1),
        HirNode(1, "conversion", MONEY, children=(0,)),
    )
    with pytest.raises(HirContractError, match="explicit conversion policy"):
        HirModule("bad", (), nodes, (1,))


def test_capability_scopes_require_named_capabilities():
    with pytest.raises(HirContractError, match="at least one capability"):
        HirModule("bad", (), (HirNode(0, "capability_scope", I32),), (0,))


def test_duplicate_capabilities_are_rejected():
    with pytest.raises(HirContractError, match="must be unique"):
        HirNode(0, "call", I32, capabilities=("io", "io"))


def test_invalid_json_is_wrapped_as_contract_error():
    with pytest.raises(HirContractError, match="invalid HIR JSON"):
        load_hir_json("{")


def test_non_object_json_is_rejected():
    with pytest.raises(HirContractError, match="root must be an object"):
        load_hir_json("[]")


@pytest.mark.parametrize(
    "data,message",
    [
        ({}, "expected HIR schema"),
        ({"schema": HIR_SCHEMA, "name": "", "bindings": [], "nodes": [], "roots": []}, "module name"),
        ({"schema": HIR_SCHEMA, "name": "m", "bindings": {}, "nodes": [], "roots": []}, "must be lists"),
        ({"schema": HIR_SCHEMA, "name": "m", "bindings": [1], "nodes": [], "roots": []}, "binding entries"),
        ({"schema": HIR_SCHEMA, "name": "m", "bindings": [], "nodes": [1], "roots": []}, "node entries"),
    ],
)
def test_malformed_hir_objects_are_rejected(data, message):
    with pytest.raises(HirContractError, match=message):
        parse_hir(data)


def test_semantic_metadata_survives_round_trip():
    module = sample_module()
    decoded = load_hir_json(canonical_hir_json(module))
    binary = decoded.nodes[2]
    conversion = decoded.nodes[3]
    function = decoded.nodes[8]
    assert binary.numeric_policy == "exact"
    assert conversion.conversion_policy == "checked"
    assert function.capabilities == ("allocate",)
    assert decoded.bindings[1].ownership == "owned"
    assert decoded.nodes[5].ownership == "borrowed"
