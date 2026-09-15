"""Canonical bootstrap AST contract for ``bootstrap-expression-v1`` trees.

The Merit-native parser currently emits compact postorder ``ExpressionNode``
records.  This module defines the source-oriented AST boundary that follows
that parser representation.  It deliberately performs no name resolution,
type checking, ownership analysis, or backend lowering.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Iterable, Sequence


class AstContractError(ValueError):
    """Raised when parser records violate the versioned expression contract."""


KIND_IDENTIFIER = 30
KIND_EXACT_NUMERIC = 31
KIND_STRING = 32
KIND_GROUP = 33
KIND_CALL = 34
KIND_FIELD = 35
KIND_GENERIC_APPLY = 36
KIND_SEQUENCE = 37
KIND_FIELD_INITIALIZER = 38
KIND_INVALID = 39
KIND_EQUAL = 40
KIND_NOT_EQUAL = 41
KIND_GREATER_EQUAL = 42
KIND_LESS_EQUAL = 43
KIND_GREATER = 44
KIND_LESS = 45
KIND_ADD = 50
KIND_SUBTRACT = 51
KIND_MULTIPLY = 60
KIND_DIVIDE = 61
KIND_CONSTRUCTOR = 70

_KIND_NAMES = {
    KIND_IDENTIFIER: "identifier", KIND_EXACT_NUMERIC: "exact_numeric",
    KIND_STRING: "string", KIND_CALL: "call", KIND_FIELD: "field",
    KIND_GENERIC_APPLY: "generic_apply", KIND_SEQUENCE: "sequence",
    KIND_FIELD_INITIALIZER: "field_initializer", KIND_INVALID: "invalid",
    KIND_EQUAL: "equal", KIND_NOT_EQUAL: "not_equal",
    KIND_GREATER_EQUAL: "greater_equal", KIND_LESS_EQUAL: "less_equal",
    KIND_GREATER: "greater", KIND_LESS: "less", KIND_ADD: "add",
    KIND_SUBTRACT: "subtract", KIND_MULTIPLY: "multiply",
    KIND_DIVIDE: "divide", KIND_CONSTRUCTOR: "constructor",
}

_ATOMS = {KIND_IDENTIFIER, KIND_EXACT_NUMERIC, KIND_STRING, KIND_INVALID}
_BINARY = {KIND_EQUAL, KIND_NOT_EQUAL, KIND_GREATER_EQUAL, KIND_LESS_EQUAL,
           KIND_GREATER, KIND_LESS, KIND_ADD, KIND_SUBTRACT, KIND_MULTIPLY,
           KIND_DIVIDE}
_OPTIONAL_RIGHT = {KIND_CALL, KIND_GENERIC_APPLY, KIND_SEQUENCE,
                   KIND_FIELD_INITIALIZER, KIND_CONSTRUCTOR}
_REQUIRED_PAIR = _BINARY | {KIND_FIELD}


@dataclass(frozen=True, slots=True)
class AstNode:
    """A canonical, immutable AST node with deterministic source provenance."""

    kind: str
    start: int
    length: int
    children: tuple["AstNode", ...] = ()
    grouping_origins: tuple[tuple[int, int], ...] = ()

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "kind": self.kind,
            "start": self.start,
            "length": self.length,
            "children": [child.to_data() for child in self.children],
        }
        if self.grouping_origins:
            data["grouping_origins"] = [list(origin) for origin in self.grouping_origins]
        return data


ExpressionRecord = tuple[int, int, int, int, int]


def _validate_span(start: int, length: int) -> None:
    if start < 0:
        raise AstContractError(f"negative source start: {start}")
    if length < 0:
        raise AstContractError(f"negative source length: {length}")


def _child(nodes: Sequence[AstNode | None], index: int, current: int) -> AstNode:
    if index < 0 or index >= current:
        raise AstContractError(f"child index {index} is not before node {current}")
    child = nodes[index]
    if child is None:
        raise AstContractError(f"child index {index} has no canonical AST node")
    return child


def lower_expression_ast(
    records: Iterable[ExpressionRecord], *, root_index: int | None = None
) -> AstNode:
    """Lower postorder parser records into ``bootstrap-ast-v1``.

    Parenthesized-group records (kind ``33``) disappear as semantic nodes. The
    removed source span is retained on the lowered child as grouping provenance.
    All other records preserve their parser span and deterministic child order.
    """

    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise AstContractError("expression record stream is empty")

    lowered: list[AstNode | None] = []
    for index, record in enumerate(materialized):
        if len(record) != 5:
            raise AstContractError(f"node {index} does not contain five fields")
        kind, start, length, left, right = record
        _validate_span(start, length)

        if kind == KIND_GROUP:
            child = _child(lowered, left, index)
            lowered.append(
                replace(
                    child,
                    grouping_origins=child.grouping_origins + ((start, length),),
                )
            )
            continue

        name = _KIND_NAMES.get(kind)
        if name is None:
            raise AstContractError(f"unknown bootstrap expression kind {kind} at node {index}")

        children: list[AstNode] = []
        if kind in _ATOMS:
            if left != -1 or right != -1:
                raise AstContractError(f"atom node {index} unexpectedly has children")
        elif kind in _REQUIRED_PAIR:
            children.append(_child(lowered, left, index))
            children.append(_child(lowered, right, index))
        elif kind in _OPTIONAL_RIGHT:
            children.append(_child(lowered, left, index))
            if right != -1:
                children.append(_child(lowered, right, index))
        else:  # Defensive: every known kind must be classified above.
            raise AstContractError(f"unclassified bootstrap expression kind {kind}")

        lowered.append(AstNode(name, start, length, tuple(children)))

    selected = len(lowered) - 1 if root_index is None else root_index
    if selected < 0 or selected >= len(lowered):
        raise AstContractError(f"root index {selected} is outside the record stream")
    root = lowered[selected]
    if root is None:
        raise AstContractError(f"root index {selected} has no canonical AST node")
    return root


def canonical_ast_json(node: AstNode) -> str:
    """Return stable JSON suitable for differential compiler comparison."""

    return json.dumps(node.to_data(), sort_keys=True, separators=(",", ":"))
