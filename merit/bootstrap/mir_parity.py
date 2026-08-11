"""Canonical adapter for Merit-native primitive expression MIR records."""

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


# kind,start,length,result,left,right,symbol,type_code,numeric_policy,binding_id,hir_node_id
NativeMirExpressionRecord = tuple[int, int, int, int, int, int, int, int, int, int, int]

_KIND_CONST = 1
_KIND_BINARY = 2
_KIND_GROUP_ALIAS = 3
_KIND_BINDING = 4
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
_POLICIES = {_POLICY_EXACT: "exact", _POLICY_CHECKED: "checked"}


class NativeMirExpressionError(ValueError):
    """Raised when a flat Merit-native MIR record violates the measured slice."""


def lower_native_expression_mir_records(
    records: Iterable[NativeMirExpressionRecord],
    source: str,
    *,
    module_name: str,
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    """Reconstruct canonical single-block MIR without re-lowering HIR.

    The native stream already contains local assignment, operand-local identity,
    instruction policy, and canonical HIR identity. This adapter validates those
    decisions and serializes them into ``bootstrap-mir-v1``.
    """

    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise NativeMirExpressionError("native expression MIR record stream is empty")
    if not module_name:
        raise NativeMirExpressionError("MIR parity module name must be non-empty")
    types: dict[int, MirType] = {1: MirType("i64"), 2: MirType("bool")}
    if type_names:
        for code, type_ in type_names.items():
            if code <= 0:
                raise NativeMirExpressionError("MIR type codes must be positive")
            if code in types and types[code] != type_:
                raise NativeMirExpressionError(f"MIR type code {code} has conflicting definitions")
            types[code] = type_

    binding_names: dict[int, str] = {}
    binding_types: dict[int, MirType] = {}
    temporary_types: dict[int, tuple[MirType, int]] = {}
    instructions: list[MirInstruction] = []
    known_locals: set[int] = set()
    native_results: list[int] = []
    canonical_ids: list[int] = []

    def resolved_type(code: int, index: int) -> MirType:
        try:
            return types[code]
        except KeyError as error:
            raise NativeMirExpressionError(
                f"record {index} has unresolved MIR type code {code}"
            ) from error

    for index, record in enumerate(materialized):
        if len(record) != 11:
            raise NativeMirExpressionError(f"record {index} does not contain eleven fields")
        (
            kind,
            start,
            length,
            result,
            left,
            right,
            symbol_code,
            type_code,
            policy_code,
            binding_id,
            hir_node_id,
        ) = record
        if start < 0 or length < 0 or start + length > len(source):
            raise NativeMirExpressionError(f"record {index} span is outside source text")
        if hir_node_id < 0:
            raise NativeMirExpressionError(f"record {index} has invalid canonical HIR ID")

        if kind == _KIND_GROUP_ALIAS:
            if index == 0 or left < 0 or result != left:
                raise NativeMirExpressionError(f"group alias {index} has invalid local identity")
            if result not in known_locals:
                raise NativeMirExpressionError(f"group alias {index} references unknown local {result}")
            if right != -1 or symbol_code != 0 or policy_code != 0 or binding_id != -1:
                raise NativeMirExpressionError(f"group alias {index} has invalid structural fields")
            native_results.append(result)
            canonical_ids.append(hir_node_id)
            continue

        type_ = resolved_type(type_code, index)
        if kind == _KIND_BINDING:
            if binding_id < 0 or result != binding_id:
                raise NativeMirExpressionError(f"binding record {index} has invalid binding/local ID")
            if left != -1 or right != -1 or symbol_code != 0 or policy_code != 0:
                raise NativeMirExpressionError(f"binding record {index} has invalid instruction fields")
            name = source[start : start + length]
            if not name:
                raise NativeMirExpressionError(f"binding record {index} has empty source name")
            if binding_id in binding_names and binding_names[binding_id] != name:
                raise NativeMirExpressionError(
                    f"binding {binding_id} resolves both {binding_names[binding_id]!r} and {name!r}"
                )
            if binding_id in binding_types and binding_types[binding_id] != type_:
                raise NativeMirExpressionError(f"binding {binding_id} has inconsistent MIR types")
            binding_names[binding_id] = name
            binding_types[binding_id] = type_
            known_locals.add(result)
            native_results.append(result)
            canonical_ids.append(hir_node_id)
            continue

        if kind not in {_KIND_CONST, _KIND_BINARY}:
            raise NativeMirExpressionError(f"record {index} has unsupported MIR kind {kind}")
        if result < 0 or result in temporary_types or result in binding_names:
            raise NativeMirExpressionError(f"record {index} has duplicate/invalid result local {result}")
        temporary_types[result] = (type_, hir_node_id)
        known_locals.add(result)

        if kind == _KIND_CONST:
            if left != -1 or right != -1 or symbol_code != 0 or policy_code != _POLICY_NONE:
                raise NativeMirExpressionError(f"const record {index} has invalid instruction fields")
            if binding_id != -1:
                raise NativeMirExpressionError(f"const record {index} unexpectedly carries a binding")
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
        else:
            if left not in known_locals or right not in known_locals:
                raise NativeMirExpressionError(
                    f"binary record {index} references unknown operand locals {(left, right)}"
                )
            try:
                symbol = _SYMBOLS[symbol_code]
            except KeyError as error:
                raise NativeMirExpressionError(
                    f"binary record {index} has unknown symbol code {symbol_code}"
                ) from error
            try:
                policy = _POLICIES[policy_code]
            except KeyError as error:
                raise NativeMirExpressionError(
                    f"binary record {index} has invalid numeric policy {policy_code}"
                ) from error
            if symbol_code <= 4 and policy != "checked":
                raise NativeMirExpressionError(
                    f"arithmetic record {index} must retain checked numeric policy"
                )
            if symbol_code >= 5 and policy != "exact":
                raise NativeMirExpressionError(
                    f"comparison record {index} must retain exact numeric policy"
                )
            if binding_id != -1:
                raise NativeMirExpressionError(f"binary record {index} unexpectedly carries a binding")
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
        native_results.append(result)
        canonical_ids.append(hir_node_id)

    if binding_names and sorted(binding_names) != list(range(max(binding_names) + 1)):
        raise NativeMirExpressionError("native MIR binding IDs must be dense")
    binding_count = len(binding_names)
    temporary_ids = sorted(temporary_types)
    if temporary_ids != list(range(binding_count, binding_count + len(temporary_ids))):
        raise NativeMirExpressionError("native MIR temporary local IDs must follow bindings densely")

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
    root_local = native_results[-1]
    root_type = next(local.type for local in locals_ if local.local_id == root_local)
    function = MirFunction(
        module_name,
        root_type,
        tuple(locals_),
        (MirBlock(0, tuple(instructions), MirTerminator("return", operands=(root_local,))),),
        0,
    )
    return MirModule(module_name, (function,))


def expression_mir_parity_observations(
    case_id: str,
    reference_hir: HirModule,
    native_records: Iterable[NativeMirExpressionRecord],
    source: str,
) -> tuple[StageObservation, StageObservation]:
    """Compare canonical Python HIR->MIR with independently emitted native MIR."""

    reference = lower_expression_hir_to_mir(reference_hir)
    bootstrap = lower_native_expression_mir_records(
        native_records,
        source,
        module_name=reference_hir.name,
    )
    return (
        observe(case_id, "mir", "reference", canonical_mir_json(reference)),
        observe(case_id, "mir", "bootstrap", canonical_mir_json(bootstrap)),
    )
