"""Versioned, backend-neutral HIR contract for Merit bootstrap comparison.

This module defines the semantic interchange boundary after AST lowering and
before MIR construction.  It is intentionally independent of parser records,
Python object identity, allocation addresses, and backend-specific details.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable, Mapping, Sequence

HIR_SCHEMA = "bootstrap-hir-v1"

NODE_KINDS = frozenset({
    "module", "function", "parameter", "block", "let", "assign", "return",
    "if", "while", "match", "match_arm", "call", "field", "constructor",
    "identifier", "literal", "binary", "conversion", "contract_check",
    "capability_scope", "drop", "move", "borrow", "invalid",
})
OWNERSHIP_MODES = frozenset({"value", "owned", "borrowed", "mutable_borrow", "moved", "none"})
CONVERSION_POLICIES = frozenset({"exact", "checked", "round", "truncate", "reinterpret", "none"})
NUMERIC_POLICIES = frozenset({"exact", "checked", "wrapping", "saturating", "floating", "none"})


class HirContractError(ValueError):
    """Raised when HIR violates ``bootstrap-hir-v1``."""


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: int
    length: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.length < 0:
            raise HirContractError("source spans must be non-negative")

    def to_data(self) -> list[int]:
        return [self.start, self.length]


@dataclass(frozen=True, slots=True)
class HirType:
    name: str
    arguments: tuple["HirType", ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise HirContractError("HIR type name must be non-empty")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {"name": self.name}
        if self.arguments:
            data["arguments"] = [argument.to_data() for argument in self.arguments]
        return data


@dataclass(frozen=True, slots=True)
class HirBinding:
    binding_id: int
    name: str
    type: HirType
    mutable: bool = False
    ownership: str = "value"
    span: SourceSpan | None = None

    def __post_init__(self) -> None:
        if self.binding_id < 0:
            raise HirContractError("binding IDs must be non-negative")
        if not self.name:
            raise HirContractError("binding names must be non-empty")
        if self.ownership not in OWNERSHIP_MODES:
            raise HirContractError(f"unknown ownership mode: {self.ownership}")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "id": self.binding_id,
            "name": self.name,
            "type": self.type.to_data(),
            "mutable": self.mutable,
            "ownership": self.ownership,
        }
        if self.span is not None:
            data["span"] = self.span.to_data()
        return data


@dataclass(frozen=True, slots=True)
class HirNode:
    node_id: int
    kind: str
    type: HirType
    children: tuple[int, ...] = ()
    span: SourceSpan | None = None
    binding_id: int | None = None
    symbol: str | None = None
    value: object | None = None
    ownership: str = "none"
    numeric_policy: str = "none"
    conversion_policy: str = "none"
    capabilities: tuple[str, ...] = ()
    generic_arguments: tuple[HirType, ...] = ()

    def __post_init__(self) -> None:
        if self.node_id < 0:
            raise HirContractError("node IDs must be non-negative")
        if self.kind not in NODE_KINDS:
            raise HirContractError(f"unknown HIR node kind: {self.kind}")
        if self.binding_id is not None and self.binding_id < 0:
            raise HirContractError("binding references must be non-negative")
        if self.ownership not in OWNERSHIP_MODES:
            raise HirContractError(f"unknown ownership mode: {self.ownership}")
        if self.numeric_policy not in NUMERIC_POLICIES:
            raise HirContractError(f"unknown numeric policy: {self.numeric_policy}")
        if self.conversion_policy not in CONVERSION_POLICIES:
            raise HirContractError(f"unknown conversion policy: {self.conversion_policy}")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise HirContractError("capability requirements must be unique")
        if any(not capability for capability in self.capabilities):
            raise HirContractError("capability names must be non-empty")
        if self.generic_arguments and self.kind != "call":
            raise HirContractError("generic arguments are only valid on call nodes")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "id": self.node_id,
            "kind": self.kind,
            "type": self.type.to_data(),
            "children": list(self.children),
            "ownership": self.ownership,
            "numeric_policy": self.numeric_policy,
            "conversion_policy": self.conversion_policy,
        }
        if self.span is not None:
            data["span"] = self.span.to_data()
        if self.binding_id is not None:
            data["binding_id"] = self.binding_id
        if self.symbol is not None:
            data["symbol"] = self.symbol
        if self.value is not None:
            data["value"] = self.value
        if self.capabilities:
            data["capabilities"] = list(self.capabilities)
        if self.generic_arguments:
            data["generic_arguments"] = [argument.to_data() for argument in self.generic_arguments]
        return data


@dataclass(frozen=True, slots=True)
class HirModule:
    name: str
    bindings: tuple[HirBinding, ...]
    nodes: tuple[HirNode, ...]
    roots: tuple[int, ...]
    schema: str = HIR_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != HIR_SCHEMA:
            raise HirContractError(f"expected HIR schema {HIR_SCHEMA!r}")
        if not self.name:
            raise HirContractError("module name must be non-empty")
        _validate_module(self)

    def to_data(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "name": self.name,
            "bindings": [binding.to_data() for binding in self.bindings],
            "nodes": [node.to_data() for node in self.nodes],
            "roots": list(self.roots),
        }


def _validate_module(module: HirModule) -> None:
    binding_ids = [binding.binding_id for binding in module.bindings]
    if len(set(binding_ids)) != len(binding_ids):
        raise HirContractError("duplicate HIR binding ID")
    node_ids = [node.node_id for node in module.nodes]
    if len(set(node_ids)) != len(node_ids):
        raise HirContractError("duplicate HIR node ID")

    binding_set = set(binding_ids)
    node_set = set(node_ids)
    for root in module.roots:
        if root not in node_set:
            raise HirContractError(f"unknown root node ID: {root}")
    for node in module.nodes:
        for child in node.children:
            if child not in node_set:
                raise HirContractError(f"node {node.node_id} references unknown child {child}")
            if child >= node.node_id:
                raise HirContractError("HIR nodes must use deterministic postorder child references")
        if node.binding_id is not None and node.binding_id not in binding_set:
            raise HirContractError(
                f"node {node.node_id} references unknown binding {node.binding_id}"
            )
        if node.kind in {"identifier", "let", "assign", "parameter", "move", "borrow", "drop"}:
            if node.binding_id is None:
                raise HirContractError(f"{node.kind} node requires a binding ID")
        if node.kind == "conversion" and node.conversion_policy == "none":
            raise HirContractError("conversion nodes require an explicit conversion policy")
        if node.kind == "binary" and node.numeric_policy == "none":
            raise HirContractError("binary nodes require an explicit numeric policy")
        if node.kind == "capability_scope" and not node.capabilities:
            raise HirContractError("capability scopes require at least one capability")

    _validate_acyclic(module.nodes)


def _validate_acyclic(nodes: Sequence[HirNode]) -> None:
    by_id = {node.node_id: node for node in nodes}
    visiting: set[int] = set()
    complete: set[int] = set()

    def visit(node_id: int) -> None:
        if node_id in complete:
            return
        if node_id in visiting:
            raise HirContractError("HIR child graph contains a cycle")
        visiting.add(node_id)
        for child in by_id[node_id].children:
            visit(child)
        visiting.remove(node_id)
        complete.add(node_id)

    for node in nodes:
        visit(node.node_id)


def canonical_hir_json(module: HirModule) -> str:
    """Return deterministic compact JSON for differential comparison."""

    return json.dumps(module.to_data(), sort_keys=True, separators=(",", ":"))


def parse_hir_type(data: object) -> HirType:
    if not isinstance(data, Mapping):
        raise HirContractError("HIR type must be an object")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise HirContractError("HIR type name must be non-empty")
    raw_arguments = data.get("arguments", [])
    if not isinstance(raw_arguments, list):
        raise HirContractError("HIR type arguments must be a list")
    return HirType(name, tuple(parse_hir_type(argument) for argument in raw_arguments))


def _parse_span(data: object | None) -> SourceSpan | None:
    if data is None:
        return None
    if not isinstance(data, list) or len(data) != 2 or not all(isinstance(v, int) for v in data):
        raise HirContractError("HIR spans must be [start, length]")
    return SourceSpan(data[0], data[1])


def parse_hir(data: Mapping[str, object]) -> HirModule:
    if data.get("schema") != HIR_SCHEMA:
        raise HirContractError(f"expected HIR schema {HIR_SCHEMA!r}")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise HirContractError("module name must be non-empty")
    raw_bindings = data.get("bindings")
    raw_nodes = data.get("nodes")
    raw_roots = data.get("roots")
    if not isinstance(raw_bindings, list) or not isinstance(raw_nodes, list) or not isinstance(raw_roots, list):
        raise HirContractError("bindings, nodes, and roots must be lists")

    bindings: list[HirBinding] = []
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise HirContractError("binding entries must be objects")
        bindings.append(HirBinding(
            int(raw.get("id", -1)),
            str(raw.get("name", "")),
            parse_hir_type(raw.get("type")),
            bool(raw.get("mutable", False)),
            str(raw.get("ownership", "value")),
            _parse_span(raw.get("span")),
        ))

    nodes: list[HirNode] = []
    for raw in raw_nodes:
        if not isinstance(raw, Mapping):
            raise HirContractError("node entries must be objects")
        raw_children = raw.get("children", [])
        raw_capabilities = raw.get("capabilities", [])
        raw_generic_arguments = raw.get("generic_arguments", [])
        if not isinstance(raw_children, list) or not all(isinstance(v, int) for v in raw_children):
            raise HirContractError("node children must be integer lists")
        if not isinstance(raw_capabilities, list) or not all(isinstance(v, str) for v in raw_capabilities):
            raise HirContractError("node capabilities must be string lists")
        if not isinstance(raw_generic_arguments, list):
            raise HirContractError("node generic arguments must be type lists")
        binding_id = raw.get("binding_id")
        nodes.append(HirNode(
            int(raw.get("id", -1)),
            str(raw.get("kind", "")),
            parse_hir_type(raw.get("type")),
            tuple(raw_children),
            _parse_span(raw.get("span")),
            None if binding_id is None else int(binding_id),
            raw.get("symbol") if isinstance(raw.get("symbol"), str) else None,
            raw.get("value"),
            str(raw.get("ownership", "none")),
            str(raw.get("numeric_policy", "none")),
            str(raw.get("conversion_policy", "none")),
            tuple(raw_capabilities),
            tuple(parse_hir_type(argument) for argument in raw_generic_arguments),
        ))
    if not all(isinstance(root, int) for root in raw_roots):
        raise HirContractError("roots must be integer node IDs")
    return HirModule(name, tuple(bindings), tuple(nodes), tuple(raw_roots))


def load_hir_json(text: str) -> HirModule:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise HirContractError(f"invalid HIR JSON: {error}") from error
    if not isinstance(data, Mapping):
        raise HirContractError("HIR root must be an object")
    return parse_hir(data)
