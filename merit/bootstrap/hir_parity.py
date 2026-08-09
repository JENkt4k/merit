"""Adapters from Merit-native primitive HIR records to canonical HIR."""

from __future__ import annotations

from collections.abc import Iterable

from .hir_contract import HirModule, HirNode, HirType, SourceSpan, canonical_hir_json
from .parity import StageObservation, observe


NativeHirRecord = tuple[int, int, int, int, int, int, int, int]

_KIND_LITERAL = 1
_KIND_BINARY = 2
_TYPE_I64 = 1
_POLICY_EXACT = 1
_POLICY_CHECKED = 2
_SYMBOLS = {1: "+", 2: "-", 3: "*", 4: "/"}


class NativeHirContractError(ValueError):
    """Raised when Merit-native HIR records violate the primitive contract."""


def lower_native_primitive_hir_records(
    records: Iterable[NativeHirRecord],
    source: str,
    *,
    module_name: str = "expression",
) -> HirModule:
    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise NativeHirContractError("native HIR record stream is empty")
    if not module_name:
        raise NativeHirContractError("module name must be non-empty")

    nodes: list[HirNode] = []
    i64 = HirType("i64")
    for index, record in enumerate(materialized):
        if len(record) != 8:
            raise NativeHirContractError(f"record {index} does not contain eight fields")
        kind, start, length, left, right, symbol_code, type_code, policy_code = record
        if start < 0 or length < 0 or start + length > len(source):
            raise NativeHirContractError(f"record {index} span is outside source text")
        if type_code != _TYPE_I64:
            raise NativeHirContractError(f"record {index} has unsupported type code {type_code}")

        if kind == _KIND_LITERAL:
            if left != -1 or right != -1 or symbol_code != 0:
                raise NativeHirContractError(f"literal record {index} has invalid child/symbol fields")
            if policy_code != _POLICY_EXACT:
                raise NativeHirContractError(f"literal record {index} must use exact policy")
            nodes.append(
                HirNode(
                    index,
                    "literal",
                    i64,
                    span=SourceSpan(start, length),
                    value=source[start : start + length],
                    numeric_policy="exact",
                )
            )
            continue

        if kind == _KIND_BINARY:
            if left < 0 or right < 0 or left >= index or right >= index:
                raise NativeHirContractError(f"binary record {index} has non-postorder children")
            symbol = _SYMBOLS.get(symbol_code)
            if symbol is None:
                raise NativeHirContractError(f"binary record {index} has unknown symbol code {symbol_code}")
            if policy_code != _POLICY_CHECKED:
                raise NativeHirContractError(f"binary record {index} must use checked policy")
            nodes.append(
                HirNode(
                    index,
                    "binary",
                    i64,
                    children=(left, right),
                    span=SourceSpan(start, length),
                    symbol=symbol,
                    numeric_policy="checked",
                )
            )
            continue

        raise NativeHirContractError(f"record {index} has unsupported kind {kind}")

    return HirModule(module_name, (), tuple(nodes), (len(nodes) - 1,))


def primitive_hir_parity_observations(
    case_id: str,
    reference: HirModule,
    native_records: Iterable[NativeHirRecord],
    source: str,
) -> tuple[StageObservation, StageObservation]:
    bootstrap = lower_native_primitive_hir_records(
        native_records, source, module_name=reference.name
    )
    return (
        observe(case_id, "hir", "reference", canonical_hir_json(reference)),
        observe(case_id, "hir", "bootstrap", canonical_hir_json(bootstrap)),
    )
