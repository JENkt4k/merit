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


_KIND_NAMES = {
    30: "identifier",
    31: "exact_numeric",
    32: "string",
    34: "call",
    35: "field",
    36: "generic_apply",
    37: "sequence",
    38: "field_initializer",
    39: "invalid",
    40: "equal",
    41: "not_equal",
    42: "greater_equal",
    43: "less_equal",
    44: "greater",
    45: "less",
    50: "add",
    51: "subtract",
    60: "multiply",
    61: "divide",
    70: "constructor",
}

_ATOMS = {30, 31, 32, 39}
_BINARY = {40, 41, 42, 43, 44, 45, 50, 51, 60, 61}
_OPTIONAL_RIGHT = {34, 36, 37, 38, 70}
_REQUIRED_PAIR = _BINARY | {35}


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

        if kind == 33:
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
