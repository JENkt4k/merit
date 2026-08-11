"""Canonical adapter for Merit-native composite expression MIR records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from merit.bootstrap.hir_contract import HirModule
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
    SourceSpan,
    canonical_mir_json,
)
from merit.bootstrap.mir_expression import lower_expression_hir_to_mir
from merit.bootstrap.parity import StageObservation, observe


# kind,start,length,result,left,right,symbol_start,symbol_length,symbol_code,
# type_code,numeric_policy,binding_id,hir_node_id,owner_hir_id,ordinal
NativeMirCompositeRecord = tuple[
    int, int, int, int, int, int, int, int, int, int, int, int, int, int, int
]

_KIND_CONST = 1
_KIND_BINARY = 2
_KIND_BINDING = 3
_KIND_CALL = 4
_KIND_FIELD = 5
_KIND_CONSTRUCT = 6
_KIND_OPERAND = 7
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
_POLICIES = {1: "exact", 2: "checked"}


class NativeMirCompositeError(ValueError):
    """Raised when native composite MIR violates the measured contract."""


def lower_native_composite_mir_records(
    records: Iterable[NativeMirCompositeRecord],
    source: str,
    *,
    module_name: str,
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise NativeMirCompositeError("native composite MIR record stream is empty")
    if not module_name:
        raise NativeMirCompositeError("composite MIR module name must be non-empty")

    types: dict[int, MirType] = {1: MirType("i64"), 2: MirType("bool")}
    if type_names:
        for code, type_ in type_names.items():
            if code <= 0:
                raise NativeMirCompositeError("composite MIR type codes must be positive")
            if code in types and types[code] != type_:
                raise NativeMirCompositeError(
                    f"composite MIR type code {code} has conflicting definitions"
                )
            types[code] = type_

    binding_names: dict[int, str] = {}
    binding_types: dict[int, MirType] = {}
    temporary_types: dict[int, tuple[MirType, int]] = {}
    known_locals: set[int] = set()
    operand_markers: dict[int, dict[int, int]] = defaultdict(dict)
    instructions: list[MirInstruction] = []
    semantic_results: list[int] = []

    def resolved_type(code: int, index: int) -> MirType:
        try:
            return types[code]
        except KeyError as error:
            raise NativeMirCompositeError(
                f"record {index} has unresolved composite MIR type code {code}"
            ) from error

    def source_symbol(start: int, length: int, index: int) -> str:
        if start < 0 or length <= 0 or start + length > len(source):
            raise NativeMirCompositeError(f"record {index} has invalid resolved symbol span")
        symbol = source[start : start + length]
        if not symbol:
            raise NativeMirCompositeError(f"record {index} has empty resolved symbol")
        return symbol

    def ordered_operands(owner_hir_id: int, index: int) -> tuple[int, ...]:
        by_ordinal = operand_markers.get(owner_hir_id, {})
        if not by_ordinal:
            return ()
        ordinals = sorted(by_ordinal)
        if ordinals != list(range(len(ordinals))):
            raise NativeMirCompositeError(
                f"record {index} has non-dense operand ordinals for HIR {owner_hir_id}"
            )
        return tuple(by_ordinal[ordinal] for ordinal in ordinals)

    for index, record in enumerate(materialized):
        if len(record) != 15:
            raise NativeMirCompositeError(f"record {index} does not contain fifteen fields")
        (
            kind,
            start,
            length,
            result,
            left,
            right,
            symbol_start,
            symbol_length,
            symbol_code,
            type_code,
            policy_code,
            binding_id,
            hir_node_id,
            owner_hir_id,
            ordinal,
        ) = record

        if start < 0 or length < 0 or start + length > len(source):
            raise NativeMirCompositeError(f"record {index} span is outside source text")

        if kind == _KIND_OPERAND:
            if result < 0 or result not in known_locals:
                raise NativeMirCompositeError(
                    f"operand marker {index} references unknown local {result}"
                )
            if owner_hir_id < 0 or ordinal < 0:
                raise NativeMirCompositeError(f"operand marker {index} has invalid owner/ordinal")
            if ordinal in operand_markers[owner_hir_id]:
                raise NativeMirCompositeError(
                    f"operand marker {index} repeats ordinal {ordinal} for HIR {owner_hir_id}"
                )
            if any(
                value != expected
                for value, expected in (
                    (left, -1),
                    (right, -1),
                    (symbol_start, -1),
                    (symbol_length, 0),
                    (symbol_code, 0),
                    (type_code, 0),
                    (policy_code, 0),
                    (binding_id, -1),
                    (hir_node_id, -1),
                )
            ):
                raise NativeMirCompositeError(f"operand marker {index} has semantic fields")
            operand_markers[owner_hir_id][ordinal] = result
            continue

        if hir_node_id < 0:
            raise NativeMirCompositeError(f"record {index} has invalid canonical HIR ID")
        type_ = resolved_type(type_code, index)

        if kind == _KIND_BINDING:
            if binding_id < 0 or result != binding_id:
                raise NativeMirCompositeError(f"binding record {index} has invalid local identity")
            if any(
                value != expected
                for value, expected in (
                    (left, -1),
                    (right, -1),
                    (symbol_start, -1),
                    (symbol_length, 0),
                    (symbol_code, 0),
                    (policy_code, 0),
                    (owner_hir_id, -1),
                    (ordinal, -1),
                )
            ):
                raise NativeMirCompositeError(f"binding record {index} has instruction fields")
            name = source[start : start + length]
            if not name:
                raise NativeMirCompositeError(f"binding record {index} has empty source name")
            if binding_id in binding_names and binding_names[binding_id] != name:
                raise NativeMirCompositeError(
                    f"binding {binding_id} resolves both {binding_names[binding_id]!r} and {name!r}"
                )
            if binding_id in binding_types and binding_types[binding_id] != type_:
                raise NativeMirCompositeError(f"binding {binding_id} has inconsistent types")
            binding_names[binding_id] = name
            binding_types[binding_id] = type_
            known_locals.add(result)
            semantic_results.append(result)
            continue

        if kind not in {_KIND_CONST, _KIND_BINARY, _KIND_CALL, _KIND_FIELD, _KIND_CONSTRUCT}:
            raise NativeMirCompositeError(f"record {index} has unsupported kind {kind}")
        if result < 0 or result in temporary_types or result in binding_names:
            raise NativeMirCompositeError(f"record {index} has duplicate/invalid result local {result}")
        temporary_types[result] = (type_, hir_node_id)
        known_locals.add(result)

        if kind == _KIND_CONST:
            if any(
                value != expected
                for value, expected in (
                    (left, -1),
                    (right, -1),
                    (symbol_start, -1),
                    (symbol_length, 0),
                    (symbol_code, 0),
                    (policy_code, 0),
                    (binding_id, -1),
                    (owner_hir_id, -1),
                    (ordinal, -1),
                )
            ):
                raise NativeMirCompositeError(f"const record {index} has invalid fields")
            instructions.append(
                MirInstruction(
                    len(instructions),
                    "const",
                    result=result,
                    value=source[start : start + length],
                    span=SourceSpan(start, length),
                    ownership="value",
                )
            )
        elif kind == _KIND_BINARY:
            if left not in known_locals or right not in known_locals:
                raise NativeMirCompositeError(
                    f"binary record {index} references unknown operands {(left, right)}"
                )
            try:
                symbol = _SYMBOLS[symbol_code]
                policy = _POLICIES[policy_code]
            except KeyError as error:
                raise NativeMirCompositeError(
                    f"binary record {index} has invalid symbol/policy"
                ) from error
            if symbol_code <= 4 and policy != "checked":
                raise NativeMirCompositeError(f"arithmetic record {index} must be checked")
            if symbol_code >= 5 and policy != "exact":
                raise NativeMirCompositeError(f"comparison record {index} must be exact")
            instructions.append(
                MirInstruction(
                    len(instructions),
                    "binary",
                    result=result,
                    operands=(left, right),
                    symbol=symbol,
                    span=SourceSpan(start, length),
                    numeric_policy=policy,
                )
            )
        elif kind == _KIND_CALL:
            symbol = source_symbol(symbol_start, symbol_length, index)
            operands = ordered_operands(hir_node_id, index)
            instructions.append(
                MirInstruction(
                    len(instructions),
                    "call",
                    result=result,
                    operands=operands,
                    symbol=symbol,
                    span=SourceSpan(start, length),
                    ownership="value",
                )
            )
        elif kind == _KIND_FIELD:
            if left not in known_locals:
                raise NativeMirCompositeError(
                    f"field record {index} references unknown receiver local {left}"
                )
            symbol = source_symbol(symbol_start, symbol_length, index)
            instructions.append(
                MirInstruction(
                    len(instructions),
                    "load_field",
                    result=result,
                    operands=(left,),
                    symbol=symbol,
                    span=SourceSpan(start, length),
                    ownership="value",
                )
            )
        else:
            symbol = source_symbol(symbol_start, symbol_length, index)
            operands = ordered_operands(hir_node_id, index)
            instructions.append(
                MirInstruction(
                    len(instructions),
                    "construct",
                    result=result,
                    operands=operands,
                    symbol=symbol,
                    span=SourceSpan(start, length),
                    ownership="value",
                )
            )
        semantic_results.append(result)

    if binding_names and sorted(binding_names) != list(range(max(binding_names) + 1)):
        raise NativeMirCompositeError("native composite MIR binding IDs must be dense")
    binding_count = len(binding_names)
    temporary_ids = sorted(temporary_types)
    if temporary_ids != list(range(binding_count, binding_count + len(temporary_ids))):
        raise NativeMirCompositeError(
            "native composite MIR temporary IDs must follow bindings densely"
        )

    locals_: list[MirLocal] = [
        MirLocal(
            binding_id,
            binding_names[binding_id],
            binding_types[binding_id],
            source_binding_id=binding_id,
        )
        for binding_id in sorted(binding_names)
    ]
    locals_.extend(
        MirLocal(local_id, f"_t{hir_node_id}", type_)
        for local_id, (type_, hir_node_id) in sorted(temporary_types.items())
    )
    if not semantic_results:
        raise NativeMirCompositeError("native composite MIR contains no semantic result")
    root_local = semantic_results[-1]
    root_type = next(local.type for local in locals_ if local.local_id == root_local)
    function = MirFunction(
        module_name,
        root_type,
        tuple(locals_),
        (MirBlock(0, tuple(instructions), MirTerminator("return", operands=(root_local,))),),
        0,
    )
    return MirModule(module_name, (function,))


def composite_mir_parity_observations(
    case_id: str,
    reference_hir: HirModule,
    native_records: Iterable[NativeMirCompositeRecord],
    source: str,
    *,
    type_names: Mapping[int, MirType] | None = None,
) -> tuple[StageObservation, StageObservation]:
    reference = lower_expression_hir_to_mir(reference_hir)
    bootstrap = lower_native_composite_mir_records(
        native_records,
        source,
        module_name=reference_hir.name,
        type_names=type_names,
    )
    return (
        observe(case_id, "mir", "reference", canonical_mir_json(reference)),
        observe(case_id, "mir", "bootstrap", canonical_mir_json(bootstrap)),
    )
