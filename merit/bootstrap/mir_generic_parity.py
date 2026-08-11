"""Canonical adapter for Merit-native generic-call MIR records."""

from __future__ import annotations

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


# kind,start,length,result,operand,symbol_start,symbol_length,type_code,
# specialization_type_code,hir_node_id,owner_hir_id,ordinal
NativeMirGenericRecord = tuple[int, int, int, int, int, int, int, int, int, int, int, int]

_KIND_CONST = 1
_KIND_CALL = 2
_KIND_OPERAND = 3


class NativeMirGenericError(ValueError):
    """Raised when native generic MIR violates the measured contract."""


def lower_native_generic_mir_records(
    records: Iterable[NativeMirGenericRecord],
    source: str,
    *,
    module_name: str,
    type_names: Mapping[int, MirType],
) -> MirModule:
    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise NativeMirGenericError("native generic MIR record stream is empty")
    if not module_name:
        raise NativeMirGenericError("generic MIR module name must be non-empty")

    known_locals: set[int] = set()
    temporary_types: dict[int, tuple[MirType, int]] = {}
    operand_by_owner: dict[int, dict[int, int]] = {}
    instructions: list[MirInstruction] = []
    root_local: int | None = None

    def resolved_type(code: int, index: int) -> MirType:
        try:
            return type_names[code]
        except KeyError as error:
            raise NativeMirGenericError(
                f"record {index} has unresolved generic MIR type code {code}"
            ) from error

    def span_text(start: int, length: int, index: int) -> str:
        if start < 0 or length <= 0 or start + length > len(source):
            raise NativeMirGenericError(f"record {index} has invalid symbol span")
        return source[start : start + length]

    for index, record in enumerate(materialized):
        if len(record) != 12:
            raise NativeMirGenericError(f"record {index} does not contain twelve fields")
        (
            kind, start, length, result, operand, symbol_start, symbol_length,
            type_code, specialization_type_code, hir_node_id, owner_hir_id, ordinal,
        ) = record
        if start < 0 or length < 0 or start + length > len(source):
            raise NativeMirGenericError(f"record {index} span is outside source text")

        if kind == _KIND_OPERAND:
            if result not in known_locals:
                raise NativeMirGenericError(
                    f"operand marker {index} references unknown local {result}"
                )
            if owner_hir_id < 0 or ordinal < 0:
                raise NativeMirGenericError(f"operand marker {index} has invalid owner/ordinal")
            if any(value != expected for value, expected in (
                (operand, -1), (symbol_start, -1), (symbol_length, 0),
                (type_code, 0), (specialization_type_code, 0), (hir_node_id, -1),
            )):
                raise NativeMirGenericError(f"operand marker {index} has semantic fields")
            owner = operand_by_owner.setdefault(owner_hir_id, {})
            if ordinal in owner:
                raise NativeMirGenericError(
                    f"operand marker {index} repeats ordinal {ordinal} for HIR {owner_hir_id}"
                )
            owner[ordinal] = result
            continue

        if result < 0 or result in known_locals or hir_node_id < 0:
            raise NativeMirGenericError(f"record {index} has invalid result/HIR identity")
        type_ = resolved_type(type_code, index)
        temporary_types[result] = (type_, hir_node_id)
        known_locals.add(result)
        root_local = result

        if kind == _KIND_CONST:
            if any(value != expected for value, expected in (
                (operand, -1), (symbol_start, -1), (symbol_length, 0),
                (specialization_type_code, 0), (owner_hir_id, -1), (ordinal, -1),
            )):
                raise NativeMirGenericError(f"const record {index} has invalid fields")
            instructions.append(MirInstruction(
                len(instructions), "const", result=result,
                value=source[start : start + length], span=SourceSpan(start, length),
                ownership="value",
            ))
            continue

        if kind != _KIND_CALL:
            raise NativeMirGenericError(f"record {index} has unsupported kind {kind}")
        if operand != -1 or owner_hir_id != -1 or ordinal != -1:
            raise NativeMirGenericError(f"call record {index} has invalid structural fields")
        if specialization_type_code <= 0:
            raise NativeMirGenericError(f"call record {index} lacks specialization identity")
        specialization = resolved_type(specialization_type_code, index)
        by_ordinal = operand_by_owner.get(hir_node_id, {})
        ordinals = sorted(by_ordinal)
        if ordinals != list(range(len(ordinals))):
            raise NativeMirGenericError(
                f"call record {index} has non-dense operand ordinals for HIR {hir_node_id}"
            )
        operands = tuple(by_ordinal[value] for value in ordinals)
        instructions.append(MirInstruction(
            len(instructions), "call", result=result, operands=operands,
            symbol=span_text(symbol_start, symbol_length, index),
            span=SourceSpan(start, length), ownership="value",
            specialization=(specialization,),
        ))

    if root_local is None:
        raise NativeMirGenericError("native generic MIR contains no semantic result")
    local_ids = sorted(temporary_types)
    if local_ids != list(range(len(local_ids))):
        raise NativeMirGenericError("native generic MIR temporary IDs must be dense")
    locals_ = tuple(
        MirLocal(local_id, f"_t{hir_node_id}", type_)
        for local_id, (type_, hir_node_id) in sorted(temporary_types.items())
    )
    root_type = temporary_types[root_local][0]
    function = MirFunction(
        module_name,
        root_type,
        locals_,
        (MirBlock(0, tuple(instructions), MirTerminator("return", operands=(root_local,))),),
        0,
    )
    return MirModule(module_name, (function,))


def generic_mir_parity_observations(
    case_id: str,
    reference_hir: HirModule,
    native_records: Iterable[NativeMirGenericRecord],
    source: str,
    *,
    type_names: Mapping[int, MirType],
) -> tuple[StageObservation, StageObservation]:
    reference = lower_expression_hir_to_mir(reference_hir)
    bootstrap = lower_native_generic_mir_records(
        native_records, source, module_name=reference_hir.name, type_names=type_names
    )
    return (
        observe(case_id, "mir", "reference", canonical_mir_json(reference)),
        observe(case_id, "mir", "bootstrap", canonical_mir_json(bootstrap)),
    )
