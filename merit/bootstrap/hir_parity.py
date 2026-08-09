"""Adapters from Merit-native executable HIR records to canonical HIR."""

from __future__ import annotations

from collections.abc import Iterable

from .hir_contract import (
    HirBinding,
    HirModule,
    HirNode,
    HirType,
    SourceSpan,
    canonical_hir_json,
)
from .parity import StageObservation, observe


NativeHirRecord = tuple[int, int, int, int, int, int, int, int, int]

_KIND_LITERAL = 1
_KIND_ARITHMETIC = 2
_KIND_GROUP_ALIAS = 3
_KIND_IDENTIFIER = 4
_KIND_COMPARISON = 5
_TYPE_I64 = 1
_TYPE_BOOL = 2
_POLICY_NONE = 0
_POLICY_EXACT = 1
_POLICY_CHECKED = 2
_SYMBOLS = {
    1: "+",
    2: "-",
    3: "*",
    4: "/",
    5: "==",
    6: "!=",
    7: ">=",
    8: "<=",
    9: ">",
    10: "<",
}


class NativeHirContractError(ValueError):
    """Raised when Merit-native HIR records violate the executable contract."""


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
    native_to_canonical: dict[int, int] = {}
    binding_names: dict[int, str] = {}
    i64 = HirType("i64")
    bool_type = HirType("bool")

    def child_id(native_index: int, current: int) -> int:
        if native_index < 0 or native_index >= current:
            raise NativeHirContractError(
                f"record {current} has non-postorder child {native_index}"
            )
        try:
            return native_to_canonical[native_index]
        except KeyError as error:
            raise NativeHirContractError(
                f"record {current} references unresolved child {native_index}"
            ) from error

    for index, record in enumerate(materialized):
        if len(record) != 9:
            raise NativeHirContractError(f"record {index} does not contain nine fields")
        (
            kind,
            start,
            length,
            left,
            right,
            symbol_code,
            type_code,
            policy_code,
            binding_id,
        ) = record
        if start < 0 or length < 0 or start + length > len(source):
            raise NativeHirContractError(f"record {index} span is outside source text")

        if kind == _KIND_GROUP_ALIAS:
            if (
                right != -1
                or symbol_code != 0
                or policy_code != _POLICY_NONE
                or binding_id != -1
            ):
                raise NativeHirContractError(f"group alias {index} has invalid fields")
            native_to_canonical[index] = child_id(left, index)
            continue

        if kind == _KIND_LITERAL:
            if type_code != _TYPE_I64:
                raise NativeHirContractError(
                    f"record {index} has unsupported type code {type_code}"
                )
            if left != -1 or right != -1 or symbol_code != 0 or binding_id != -1:
                raise NativeHirContractError(
                    f"literal record {index} has invalid child/symbol fields"
                )
            if policy_code != _POLICY_EXACT:
                raise NativeHirContractError(f"literal record {index} must use exact policy")
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "literal",
                    i64,
                    span=SourceSpan(start, length),
                    value=source[start : start + length],
                    numeric_policy="exact",
                )
            )
            native_to_canonical[index] = node_id
            continue

        if kind == _KIND_IDENTIFIER:
            if type_code != _TYPE_I64:
                raise NativeHirContractError(
                    f"identifier record {index} has unsupported type code {type_code}"
                )
            if left != -1 or right != -1 or symbol_code != 0 or policy_code != _POLICY_NONE:
                raise NativeHirContractError(f"identifier record {index} has invalid fields")
            if binding_id < 0:
                raise NativeHirContractError(f"identifier record {index} has invalid binding ID")
            name = source[start : start + length]
            previous = binding_names.get(binding_id)
            if previous is not None and previous != name:
                raise NativeHirContractError(
                    f"binding {binding_id} resolves both {previous!r} and {name!r}"
                )
            binding_names[binding_id] = name
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "identifier",
                    i64,
                    span=SourceSpan(start, length),
                    binding_id=binding_id,
                    ownership="value",
                )
            )
            native_to_canonical[index] = node_id
            continue

        if kind in {_KIND_ARITHMETIC, _KIND_COMPARISON}:
            left_id = child_id(left, index)
            right_id = child_id(right, index)
            symbol = _SYMBOLS.get(symbol_code)
            if symbol is None:
                raise NativeHirContractError(
                    f"binary record {index} has unknown symbol code {symbol_code}"
                )
            if binding_id != -1:
                raise NativeHirContractError(f"binary record {index} has binding ID")
            if kind == _KIND_ARITHMETIC:
                if type_code != _TYPE_I64 or not 1 <= symbol_code <= 4:
                    raise NativeHirContractError(f"arithmetic record {index} has invalid type/symbol")
                if policy_code != _POLICY_CHECKED:
                    raise NativeHirContractError(
                        f"arithmetic record {index} must use checked policy"
                    )
                result_type = i64
                policy = "checked"
            else:
                if type_code != _TYPE_BOOL or not 5 <= symbol_code <= 10:
                    raise NativeHirContractError(f"comparison record {index} has invalid type/symbol")
                if policy_code != _POLICY_EXACT:
                    raise NativeHirContractError(
                        f"comparison record {index} must use exact policy"
                    )
                result_type = bool_type
                policy = "exact"
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "binary",
                    result_type,
                    children=(left_id, right_id),
                    span=SourceSpan(start, length),
                    symbol=symbol,
                    numeric_policy=policy,
                )
            )
            native_to_canonical[index] = node_id
            continue

        raise NativeHirContractError(f"record {index} has unsupported kind {kind}")

    if not nodes:
        raise NativeHirContractError("native HIR stream contains no semantic nodes")
    if binding_names:
        expected_ids = list(range(max(binding_names) + 1))
        if sorted(binding_names) != expected_ids:
            raise NativeHirContractError("native binding IDs must be dense first-occurrence IDs")
    bindings = tuple(
        HirBinding(binding_id, binding_names[binding_id], i64)
        for binding_id in sorted(binding_names)
    )
    root = native_to_canonical[len(materialized) - 1]
    return HirModule(module_name, bindings, tuple(nodes), (root,))


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
