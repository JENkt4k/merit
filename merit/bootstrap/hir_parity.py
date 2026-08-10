"""Adapters from Merit-native executable HIR records to canonical HIR."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

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
_KIND_CALL = 6
_KIND_FIELD = 7
_KIND_ARGUMENT_SEQUENCE = 8
_KIND_SYMBOL_REFERENCE = 9
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
    type_names: Mapping[int, HirType] | None = None,
) -> HirModule:
    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise NativeHirContractError("native HIR record stream is empty")
    if not module_name:
        raise NativeHirContractError("module name must be non-empty")

    i64 = HirType("i64")
    bool_type = HirType("bool")
    types = {_TYPE_I64: i64, _TYPE_BOOL: bool_type}
    if type_names is not None:
        for code, type_ in type_names.items():
            if code <= 0:
                raise NativeHirContractError("native HIR type codes must be positive")
            existing = types.get(code)
            if existing is not None and existing != type_:
                raise NativeHirContractError(f"type code {code} has conflicting definitions")
            types[code] = type_

    nodes: list[HirNode] = []
    native_to_canonical: dict[int, int] = {}
    argument_lists: dict[int, tuple[int, ...]] = {}
    symbol_references: dict[int, str] = {}
    binding_names: dict[int, str] = {}
    binding_types: dict[int, HirType] = {}

    def resolved_type(code: int, current: int) -> HirType:
        try:
            return types[code]
        except KeyError as error:
            raise NativeHirContractError(
                f"record {current} has unsupported type code {code}"
            ) from error

    def child_id(native_index: int, current: int) -> int:
        if native_index < 0 or native_index >= current:
            raise NativeHirContractError(
                f"record {current} has non-postorder child {native_index}"
            )
        try:
            return native_to_canonical[native_index]
        except KeyError as error:
            raise NativeHirContractError(
                f"record {current} references unresolved value child {native_index}"
            ) from error

    def argument_ids(native_index: int, current: int) -> tuple[int, ...]:
        if native_index < 0 or native_index >= current:
            raise NativeHirContractError(
                f"record {current} has non-postorder argument child {native_index}"
            )
        sequence = argument_lists.get(native_index)
        if sequence is not None:
            return sequence
        return (child_id(native_index, current),)

    def symbol_name(native_index: int, current: int) -> str:
        if native_index < 0 or native_index >= current:
            raise NativeHirContractError(
                f"record {current} has non-postorder symbol child {native_index}"
            )
        try:
            return symbol_references[native_index]
        except KeyError as error:
            raise NativeHirContractError(
                f"record {current} references non-symbol record {native_index}"
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

        if kind == _KIND_SYMBOL_REFERENCE:
            if (
                type_code != 0
                or left != -1
                or right != -1
                or symbol_code != 0
                or policy_code != _POLICY_NONE
                or binding_id != -2
            ):
                raise NativeHirContractError(f"symbol reference {index} has invalid fields")
            symbol = source[start : start + length]
            if not symbol:
                raise NativeHirContractError(f"symbol reference {index} is empty")
            symbol_references[index] = symbol
            continue

        if kind == _KIND_ARGUMENT_SEQUENCE:
            if (
                type_code != 0
                or symbol_code != 0
                or policy_code != _POLICY_NONE
                or binding_id != -1
            ):
                raise NativeHirContractError(f"argument sequence {index} has invalid fields")
            argument_lists[index] = argument_ids(left, index) + argument_ids(right, index)
            continue

        if kind == _KIND_LITERAL:
            type_ = resolved_type(type_code, index)
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
                    type_,
                    span=SourceSpan(start, length),
                    value=source[start : start + length],
                    numeric_policy="exact",
                )
            )
            native_to_canonical[index] = node_id
            continue

        if kind == _KIND_IDENTIFIER:
            type_ = resolved_type(type_code, index)
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
            previous_type = binding_types.get(binding_id)
            if previous_type is not None and previous_type != type_:
                raise NativeHirContractError(
                    f"binding {binding_id} has inconsistent resolved types"
                )
            binding_names[binding_id] = name
            binding_types[binding_id] = type_
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "identifier",
                    type_,
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

        if kind == _KIND_CALL:
            if symbol_code != 0 or policy_code != _POLICY_NONE or binding_id != -1:
                raise NativeHirContractError(f"call record {index} has invalid fields")
            result_type = resolved_type(type_code, index)
            symbol = symbol_name(left, index)
            arguments = () if right == -1 else argument_ids(right, index)
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "call",
                    result_type,
                    children=arguments,
                    span=SourceSpan(start, length),
                    symbol=symbol,
                    ownership="value",
                )
            )
            native_to_canonical[index] = node_id
            continue

        if kind == _KIND_FIELD:
            if symbol_code != 0 or policy_code != _POLICY_NONE or binding_id != -1:
                raise NativeHirContractError(f"field record {index} has invalid fields")
            result_type = resolved_type(type_code, index)
            receiver = child_id(left, index)
            symbol = symbol_name(right, index)
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "field",
                    result_type,
                    children=(receiver,),
                    span=SourceSpan(start, length),
                    symbol=symbol,
                    ownership="value",
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
        HirBinding(
            binding_id,
            binding_names[binding_id],
            binding_types[binding_id],
        )
        for binding_id in sorted(binding_names)
    )
    try:
        root = native_to_canonical[len(materialized) - 1]
    except KeyError as error:
        raise NativeHirContractError("final native HIR record is not a semantic value") from error
    return HirModule(module_name, bindings, tuple(nodes), (root,))


def primitive_hir_parity_observations(
    case_id: str,
    reference: HirModule,
    native_records: Iterable[NativeHirRecord],
    source: str,
    *,
    type_names: Mapping[int, HirType] | None = None,
) -> tuple[StageObservation, StageObservation]:
    bootstrap = lower_native_primitive_hir_records(
        native_records,
        source,
        module_name=reference.name,
        type_names=type_names,
    )
    return (
        observe(case_id, "hir", "reference", canonical_hir_json(reference)),
        observe(case_id, "hir", "bootstrap", canonical_hir_json(bootstrap)),
    )
