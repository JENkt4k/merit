"""Canonical adapter for Merit-native straight-line whole-function MIR records.

The native record stream owns function identity, source-binding/local identity,
mutability, temporary allocation, instruction ordering, operand locals, numeric
policy, statement copies, and return operands. This adapter validates and
serializes those decisions into ``bootstrap-mir-v1``; it does not re-run HIR
lowering.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
    SourceSpan,
)

NativeMirFunctionRecord = tuple[
    int, int, int, int, int, int, int, int, int, int, int, int, int, int, int, int
]

_KIND_FUNCTION = 1
_KIND_SOURCE_LOCAL = 2
_KIND_TEMPORARY = 3
_KIND_CONST = 4
_KIND_BINARY = 5
_KIND_COPY = 6
_KIND_RETURN = 7
_SYMBOLS = {
    1: "+", 2: "-", 3: "*", 4: "/",
    5: "==", 6: "!=", 7: ">=", 8: "<=", 9: ">", 10: "<",
}
_POLICIES = {1: "exact", 2: "checked"}


class NativeMirFunctionError(ValueError):
    """Raised when native straight-line function MIR violates its contract."""


def lower_native_function_mir_records(
    records: Iterable[NativeMirFunctionRecord],
    source: str,
    *,
    module_name: str,
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    materialized = tuple(tuple(int(value) for value in record) for record in records)
    if not materialized:
        raise NativeMirFunctionError("native function MIR record stream is empty")
    if not module_name:
        raise NativeMirFunctionError("MIR module name must be non-empty")
    types: dict[int, MirType] = {1: MirType("i64"), 2: MirType("bool")}
    if type_names:
        for code, type_ in type_names.items():
            if code <= 0:
                raise NativeMirFunctionError("MIR type codes must be positive")
            if code in types and types[code] != type_:
                raise NativeMirFunctionError(f"MIR type code {code} conflicts")
            types[code] = type_

    def checked_span(start: int, length: int, label: str) -> SourceSpan:
        if start < 0 or length < 0 or start + length > len(source):
            raise NativeMirFunctionError(f"{label} span is outside source text")
        return SourceSpan(start, length)

    def resolved_type(code: int, label: str) -> MirType:
        try:
            return types[code]
        except KeyError as error:
            raise NativeMirFunctionError(f"{label} has unresolved MIR type code {code}") from error

    if len(materialized[0]) != 16:
        raise NativeMirFunctionError("function header does not contain sixteen fields")
    (
        kind, start, length, record_id, result, left, right,
        symbol_start, symbol_length, symbol_code, type_code, policy_code,
        binding_id, mutable, hir_node_id, ordinal,
    ) = materialized[0]
    if kind != _KIND_FUNCTION:
        raise NativeMirFunctionError("first native function MIR record must be the function header")
    checked_span(start, length, "function")
    checked_span(symbol_start, symbol_length, "function symbol")
    function_name = source[symbol_start : symbol_start + symbol_length]
    if not function_name:
        raise NativeMirFunctionError("function symbol is empty")
    return_type = resolved_type(type_code, "function header")
    if (
        record_id != 0 or result != -1 or left != -1 or right != -1
        or symbol_code != 0 or policy_code != 0 or binding_id != -1
        or mutable != 0 or hir_node_id != -1 or ordinal != 0
    ):
        raise NativeMirFunctionError("function header carries invalid operational fields")

    locals_by_id: dict[int, MirLocal] = {}
    instructions: list[MirInstruction] = []
    return_terminator: MirTerminator | None = None
    next_local = 0
    next_instruction = 0
    source_bindings: set[int] = set()

    for index, record in enumerate(materialized[1:], start=1):
        if len(record) != 16:
            raise NativeMirFunctionError(f"record {index} does not contain sixteen fields")
        (
            kind, start, length, record_id, result, left, right,
            symbol_start, symbol_length, symbol_code, type_code, policy_code,
            binding_id, mutable, hir_node_id, ordinal,
        ) = record
        if return_terminator is not None:
            raise NativeMirFunctionError(f"record {index} appears after return")

        if kind == _KIND_SOURCE_LOCAL:
            span = checked_span(start, length, f"source local {index}")
            if record_id != next_local or ordinal != record_id:
                raise NativeMirFunctionError("source local IDs must be dense and ordered")
            if binding_id < 0 or binding_id in source_bindings:
                raise NativeMirFunctionError(f"source local {index} has invalid binding ID")
            if mutable not in {0, 1}:
                raise NativeMirFunctionError(f"source local {index} has invalid mutability")
            if any(value != -1 for value in (result, left, right, hir_node_id)):
                raise NativeMirFunctionError(f"source local {index} has invalid local fields")
            if symbol_start != start or symbol_length != length or symbol_code != 0 or policy_code != 0:
                raise NativeMirFunctionError(f"source local {index} has invalid symbol/policy fields")
            name = source[span.start : span.start + span.length]
            if not name:
                raise NativeMirFunctionError(f"source local {index} has empty name")
            locals_by_id[record_id] = MirLocal(
                record_id,
                name,
                resolved_type(type_code, f"source local {index}"),
                mutable=bool(mutable),
                source_binding_id=binding_id,
            )
            source_bindings.add(binding_id)
            next_local += 1
            continue

        if kind == _KIND_TEMPORARY:
            if record_id != next_local or ordinal != record_id:
                raise NativeMirFunctionError("temporary local IDs must follow source locals densely")
            if hir_node_id < 0:
                raise NativeMirFunctionError(f"temporary {index} has invalid HIR identity")
            if start != 0 or length != 0 or symbol_start != -1 or symbol_length != 0:
                raise NativeMirFunctionError(f"temporary {index} carries source spelling")
            if any(value != -1 for value in (result, left, right, binding_id)):
                raise NativeMirFunctionError(f"temporary {index} has invalid local fields")
            if symbol_code != 0 or policy_code != 0 or mutable != 0:
                raise NativeMirFunctionError(f"temporary {index} has invalid semantic fields")
            locals_by_id[record_id] = MirLocal(
                record_id,
                f"_t{hir_node_id}",
                resolved_type(type_code, f"temporary {index}"),
            )
            next_local += 1
            continue

        if kind == _KIND_RETURN:
            span = checked_span(start, length, "return")
            if record_id != 0 or result != -1 or right != -1:
                raise NativeMirFunctionError("return record has invalid result/id fields")
            if left >= 0 and left not in locals_by_id:
                raise NativeMirFunctionError(f"return references unknown local {left}")
            if left < -1 or hir_node_id < 0:
                raise NativeMirFunctionError("return record has invalid operand/HIR identity")
            if (
                symbol_start != -1 or symbol_length != 0 or symbol_code != 0
                or type_code != 0 or policy_code != 0 or binding_id != -1
                or mutable != 0 or ordinal != 0
            ):
                raise NativeMirFunctionError("return record carries invalid semantic fields")
            operands = () if left == -1 else (left,)
            return_terminator = MirTerminator("return", operands=operands, span=span)
            continue

        if kind not in {_KIND_CONST, _KIND_BINARY, _KIND_COPY}:
            raise NativeMirFunctionError(f"record {index} has unsupported kind {kind}")
        span = checked_span(start, length, f"instruction {index}")
        if record_id != next_instruction or ordinal != record_id:
            raise NativeMirFunctionError("instruction IDs must be dense and ordered")
        if result < 0 or result not in locals_by_id:
            raise NativeMirFunctionError(f"instruction {index} writes unknown local {result}")
        if hir_node_id < 0:
            raise NativeMirFunctionError(f"instruction {index} has invalid HIR identity")

        if kind == _KIND_CONST:
            if any(value != -1 for value in (left, right, binding_id)):
                raise NativeMirFunctionError(f"const {index} has invalid references")
            if symbol_start != -1 or symbol_length != 0 or symbol_code != 0 or policy_code != 0:
                raise NativeMirFunctionError(f"const {index} has invalid symbol/policy fields")
            if mutable != 0:
                raise NativeMirFunctionError(f"const {index} has invalid mutability")
            resolved_type(type_code, f"const {index}")
            instructions.append(MirInstruction(
                record_id,
                "const",
                result=result,
                value=source[span.start : span.start + span.length],
                span=span,
                ownership="value",
            ))
        elif kind == _KIND_BINARY:
            if left not in locals_by_id or right not in locals_by_id:
                raise NativeMirFunctionError(
                    f"binary {index} references unknown operand locals {(left, right)}"
                )
            try:
                symbol = _SYMBOLS[symbol_code]
                policy = _POLICIES[policy_code]
            except KeyError as error:
                raise NativeMirFunctionError(f"binary {index} has invalid operator/policy") from error
            if symbol_code <= 4 and policy != "checked":
                raise NativeMirFunctionError(f"arithmetic binary {index} must be checked")
            if symbol_code >= 5 and policy != "exact":
                raise NativeMirFunctionError(f"comparison binary {index} must be exact")
            if binding_id != -1 or mutable != 0 or symbol_start != -1 or symbol_length != 0:
                raise NativeMirFunctionError(f"binary {index} has invalid extra fields")
            resolved_type(type_code, f"binary {index}")
            instructions.append(MirInstruction(
                record_id,
                "binary",
                result=result,
                operands=(left, right),
                symbol=symbol,
                span=span,
                numeric_policy=policy,
            ))
        else:
            if left not in locals_by_id or right != -1:
                raise NativeMirFunctionError(f"copy {index} has invalid source local")
            if binding_id < 0 or binding_id not in source_bindings:
                raise NativeMirFunctionError(f"copy {index} has invalid binding identity")
            if locals_by_id[result].source_binding_id != binding_id:
                raise NativeMirFunctionError(f"copy {index} destination does not match binding")
            if (
                symbol_start != -1 or symbol_length != 0 or symbol_code != 0
                or type_code != 0 or policy_code != 0 or mutable != 0
            ):
                raise NativeMirFunctionError(f"copy {index} has invalid extra fields")
            instructions.append(MirInstruction(
                record_id,
                "copy",
                result=result,
                operands=(left,),
                span=span,
            ))
        next_instruction += 1

    if return_terminator is None:
        raise NativeMirFunctionError("straight-line function MIR requires an explicit return")
    if sorted(locals_by_id) != list(range(len(locals_by_id))):
        raise NativeMirFunctionError("function MIR local IDs are not dense")
    if source_bindings and sorted(source_bindings) != list(range(len(source_bindings))):
        raise NativeMirFunctionError("function MIR source binding IDs are not dense")

    function = MirFunction(
        function_name,
        return_type,
        tuple(locals_by_id[index] for index in range(len(locals_by_id))),
        (MirBlock(0, tuple(instructions), return_terminator),),
        0,
    )
    return MirModule(module_name, (function,))
