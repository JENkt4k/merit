"""Adapters that feed real bootstrap AST artifacts into the parity engine.

The Python reference parser lowers five-field ``ExpressionRecord`` streams via
``bootstrap-ast-v1``.  The Merit-native lowerer emits eight-field flat records
that carry the same semantic node fields plus grouping provenance links.  This
module reconstructs the canonical AST from those native records and produces
real parity observations without teaching the parity engine AST semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .ast_contract import (
    AstContractError, AstNode, ExpressionRecord, KIND_ADD, KIND_CALL,
    KIND_CONSTRUCTOR, KIND_DIVIDE, KIND_EQUAL, KIND_EXACT_NUMERIC, KIND_FIELD,
    KIND_FIELD_INITIALIZER, KIND_GENERIC_APPLY, KIND_GREATER,
    KIND_GREATER_EQUAL, KIND_IDENTIFIER, KIND_INVALID, KIND_LESS,
    KIND_LESS_EQUAL, KIND_MULTIPLY, KIND_NOT_EQUAL, KIND_SEQUENCE, KIND_STRING,
    KIND_SUBTRACT, canonical_ast_json, lower_expression_ast,
)
from .parity import StageObservation, observe


NativeAstRecord = tuple[int, int, int, int, int, int, int, int]

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
_REQUIRED_PAIR = {KIND_FIELD, KIND_EQUAL, KIND_NOT_EQUAL, KIND_GREATER_EQUAL,
                  KIND_LESS_EQUAL, KIND_GREATER, KIND_LESS, KIND_ADD,
                  KIND_SUBTRACT, KIND_MULTIPLY, KIND_DIVIDE}
_OPTIONAL_RIGHT = {KIND_CALL, KIND_GENERIC_APPLY, KIND_SEQUENCE,
                   KIND_FIELD_INITIALIZER, KIND_CONSTRUCTOR}


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
