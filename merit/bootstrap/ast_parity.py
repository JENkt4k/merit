"""Adapters that feed real bootstrap AST artifacts into the parity engine.

The Python reference parser lowers five-field ``ExpressionRecord`` streams via
``bootstrap-ast-v1``.  The Merit-native lowerer emits eight-field flat records
that carry the same semantic node fields plus grouping provenance links.  This
module reconstructs the canonical AST from those native records and produces
real parity observations without teaching the parity engine AST semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .ast_contract import AstContractError, AstNode, ExpressionRecord, canonical_ast_json, lower_expression_ast
from .parity import StageObservation, observe


NativeAstRecord = tuple[int, int, int, int, int, int, int, int]

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
_REQUIRED_PAIR = {35, 40, 41, 42, 43, 44, 45, 50, 51, 60, 61}
_OPTIONAL_RIGHT = {34, 36, 37, 38, 70}


def _child(records: Sequence[NativeAstRecord], index: int, current: int) -> AstNode:
    if index < 0 or index >= current:
        raise AstContractError(f"native AST child index {index} is not before node {current}")
    return _build_native_node(records, index)


def _grouping_origins(records: Sequence[NativeAstRecord], index: int) -> tuple[tuple[int, int], ...]:
    record = records[index]
    group_start, group_length, group_parent = record[5], record[6], record[7]
    if group_start < -1 or group_length < 0:
        raise AstContractError(f"invalid native AST grouping span at node {index}")
    origins: tuple[tuple[int, int], ...] = ()
    if group_parent != -1:
        if group_parent < 0 or group_parent >= index:
            raise AstContractError(
                f"native AST grouping parent {group_parent} is not before node {index}"
            )
        origins = _grouping_origins(records, group_parent)
    if group_start >= 0:
        origins += ((group_start, group_length),)
    elif group_parent != -1:
        raise AstContractError(f"native AST node {index} has grouping parent without grouping span")
    return origins


def _build_native_node(records: Sequence[NativeAstRecord], index: int) -> AstNode:
    kind, start, length, left, right, _, _, _ = records[index]
    if start < 0 or length < 0:
        raise AstContractError(f"invalid native AST source span at node {index}")
    name = _KIND_NAMES.get(kind)
    if name is None:
        raise AstContractError(f"unknown native AST kind {kind} at node {index}")

    children: list[AstNode] = []
    if kind in _ATOMS:
        if left != -1 or right != -1:
            raise AstContractError(f"native AST atom node {index} unexpectedly has children")
    elif kind in _REQUIRED_PAIR:
        children.append(_child(records, left, index))
        children.append(_child(records, right, index))
    elif kind in _OPTIONAL_RIGHT:
        children.append(_child(records, left, index))
        if right != -1:
            children.append(_child(records, right, index))
    else:
        raise AstContractError(f"unclassified native AST kind {kind} at node {index}")

    return AstNode(
        name,
        start,
        length,
        tuple(children),
        _grouping_origins(records, index),
    )


def lower_native_ast_records(
    records: Iterable[NativeAstRecord], *, root_index: int | None = None
) -> AstNode:
    """Reconstruct canonical ``bootstrap-ast-v1`` from Merit flat AST records."""

    materialized: tuple[NativeAstRecord, ...] = tuple(
        tuple(int(value) for value in record) for record in records  # type: ignore[misc]
    )
    if not materialized:
        raise AstContractError("native AST record stream is empty")
    for index, record in enumerate(materialized):
        if len(record) != 8:
            raise AstContractError(f"native AST node {index} does not contain eight fields")

    selected = len(materialized) - 1 if root_index is None else root_index
    if selected < 0 or selected >= len(materialized):
        raise AstContractError(f"native AST root index {selected} is outside the record stream")
    return _build_native_node(materialized, selected)


def ast_parity_observations(
    case_id: str,
    reference_records: Iterable[ExpressionRecord],
    native_records: Iterable[NativeAstRecord],
) -> tuple[StageObservation, StageObservation]:
    """Create reference/bootstrap AST observations from actual stage artifacts."""

    reference = canonical_ast_json(lower_expression_ast(reference_records))
    bootstrap = canonical_ast_json(lower_native_ast_records(native_records))
    return (
        observe(case_id, "ast", "reference", reference),
        observe(case_id, "ast", "bootstrap", bootstrap),
    )
