"""Adapter from Merit-native whole-function assembly records to bootstrap-mir-v1.

The native pipeline owns local/instruction identities, contract placement, CFG
shape, capability identities, and instruction provenance.  This module validates
those decisions and materializes canonical MIR; it does not re-run source, HIR,
or ownership lowering.
"""

from __future__ import annotations

from collections import defaultdict
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

BodyRecord = tuple[int, ...]
ContractRecord = tuple[int, ...]
ContractLocalRecord = tuple[int, ...]
InstructionSourceRecord = tuple[int, ...]
CfgRecord = tuple[int, ...]
PlacementRecord = tuple[int, ...]

_SYMBOLS = {1: "+", 2: "-", 3: "*", 4: "/", 5: "==", 6: "!=", 7: ">=", 8: "<=", 9: ">", 10: "<"}
_POLICIES = {1: "exact", 2: "checked"}
_BODY_CONSTRUCT = 9
_BODY_ENUM_TAG_LOAD = 10
_BODY_ENUM_PAYLOAD_LOAD = 11
_COPY_PAYLOAD_ENUM_TYPE_CODE_BASE = 1000


class NativeWholeFunctionMirError(ValueError):
    """Raised when assembled native records violate bootstrap-mir-v1."""


def _tuples(values: Iterable[tuple[int, ...]], width: int, label: str) -> tuple[tuple[int, ...], ...]:
    result = tuple(tuple(int(value) for value in row) for row in values)
    for index, row in enumerate(result):
        if len(row) != width:
            raise NativeWholeFunctionMirError(f"{label} record {index} must contain {width} fields")
    return result


def lower_native_whole_function_assembly(
    *,
    source: str,
    module_name: str,
    body_records: Iterable[BodyRecord],
    contract_records: Iterable[ContractRecord],
    contract_locals: Iterable[ContractLocalRecord],
    instruction_sources: Iterable[InstructionSourceRecord],
    cfg_records: Iterable[CfgRecord],
    placements: Iterable[PlacementRecord],
    capability_ids: Iterable[int],
    capability_names: Mapping[int, str],
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    """Materialize one canonical function from already-resolved native records."""

    body = _tuples(body_records, 16, "body")
    contracts = _tuples(contract_records, 12, "contract")
    contract_local_rows = _tuples(contract_locals, 5, "contract local")
    sources = _tuples(instruction_sources, 8, "instruction source")
    cfg = _tuples(cfg_records, 7, "CFG")
    placement_rows = _tuples(placements, 3, "placement")
    if not body or body[0][0] != 1:
        raise NativeWholeFunctionMirError("body records must begin with a function header")
    if not module_name:
        raise NativeWholeFunctionMirError("module name must be non-empty")

    types: dict[int, MirType] = {1: MirType("i64"), 2: MirType("bool")}
    if type_names:
        types.update(type_names)

    def resolved_type(code: int, label: str) -> MirType:
        if code >= _COPY_PAYLOAD_ENUM_TYPE_CODE_BASE:
            return MirType(f"enum_copy_payload_{code - _COPY_PAYLOAD_ENUM_TYPE_CODE_BASE}")
        try:
            return types[code]
        except KeyError as error:
            raise NativeWholeFunctionMirError(f"{label} has unresolved type code {code}") from error

    def span(start: int, length: int, label: str) -> SourceSpan:
        if start < 0 or length < 0 or start + length > len(source):
            raise NativeWholeFunctionMirError(f"{label} span is outside source")
        return SourceSpan(start, length)

    header = body[0]
    _, start, length, record_id, result, left, right, symbol_start, symbol_length, symbol_code, type_code, policy, binding_id, mutable, hir_id, ordinal = header
    if any((record_id, result + 1, left + 1, right + 1, symbol_code, policy, binding_id + 1, mutable, hir_id + 1, ordinal)):
        raise NativeWholeFunctionMirError("function header carries invalid operational fields")
    span(start, length, "function")
    name_span = span(symbol_start, symbol_length, "function symbol")
    function_name = source[name_span.start : name_span.start + name_span.length]
    if not function_name:
        raise NativeWholeFunctionMirError("function name is empty")
    return_type = resolved_type(type_code, "function")

    locals_by_id: dict[int, MirLocal] = {}
    body_instructions: dict[int, MirInstruction] = {}
    for index, row in enumerate(body[1:], start=1):
        kind, start, length, rid, result, left, right, symbol_start, symbol_length, symbol_code, type_code, policy, binding_id, mutable, hir_id, ordinal = row
        if kind == 2:
            local_span = span(start, length, f"body local {index}")
            if rid in locals_by_id or rid < 0 or binding_id < 0 or mutable not in {0, 1}:
                raise NativeWholeFunctionMirError(f"body local {index} is invalid")
            locals_by_id[rid] = MirLocal(rid, source[local_span.start:local_span.start + local_span.length], resolved_type(type_code, f"body local {index}"), mutable=bool(mutable), source_binding_id=binding_id)
        elif kind == 3:
            if rid in locals_by_id or rid < 0 or hir_id < 0:
                raise NativeWholeFunctionMirError(f"body temporary {index} is invalid")
            locals_by_id[rid] = MirLocal(rid, f"_t{hir_id}", resolved_type(type_code, f"body temporary {index}"))
        elif kind in {4, 5, 6, 8, _BODY_CONSTRUCT, _BODY_ENUM_TAG_LOAD, _BODY_ENUM_PAYLOAD_LOAD}:
            if rid in body_instructions or rid < 0:
                raise NativeWholeFunctionMirError(f"body instruction {index} has duplicate/invalid ID")
            instruction_span = span(start, length, f"body instruction {index}")
            if kind == 4:
                body_instructions[rid] = MirInstruction(rid, "const", result=result, value=int(source[instruction_span.start:instruction_span.start + instruction_span.length]), span=instruction_span, ownership="value")
            elif kind == 5:
                try:
                    symbol = _SYMBOLS[symbol_code]
                    numeric_policy = _POLICIES[policy]
                except KeyError as error:
                    raise NativeWholeFunctionMirError(f"body binary {index} has invalid operator/policy") from error
                body_instructions[rid] = MirInstruction(rid, "binary", result=result, operands=(left, right), symbol=symbol, span=instruction_span, numeric_policy=numeric_policy)
            elif kind == 6:
                body_instructions[rid] = MirInstruction(rid, "copy", result=result, operands=(left,), span=instruction_span)
            elif kind == 8:
                if result != -1 or left < 0:
                    raise NativeWholeFunctionMirError(f"body print {index} has invalid operands")
                body_instructions[rid] = MirInstruction(rid, "print", operands=(left,), span=instruction_span)
            elif kind == _BODY_CONSTRUCT:
                if result < 0 or left < 0 or symbol_code < 0 or type_code < _COPY_PAYLOAD_ENUM_TYPE_CODE_BASE:
                    raise NativeWholeFunctionMirError(f"body enum construct {index} is invalid")
                body_instructions[rid] = MirInstruction(
                    rid, "construct", result=result, operands=(left,), symbol=f"variant_{symbol_code}",
                    span=instruction_span, ownership="value",
                )
            elif kind == _BODY_ENUM_TAG_LOAD:
                if result < 0 or left < 0:
                    raise NativeWholeFunctionMirError(f"body enum tag load {index} is invalid")
                body_instructions[rid] = MirInstruction(
                    rid, "load_field", result=result, operands=(left,), symbol="tag", span=instruction_span,
                )
            else:
                if result < 0 or left < 0:
                    raise NativeWholeFunctionMirError(f"body enum payload load {index} is invalid")
                body_instructions[rid] = MirInstruction(
                    rid, "load_field", result=result, operands=(left,), symbol="payload", span=instruction_span,
                )
        elif kind == 7:
            # CFG records own return placement/operands after structured assembly.
            continue
        else:
            raise NativeWholeFunctionMirError(f"unsupported body record kind {kind}")

    for local_id, source_local_id, local_type, contract_kind, clause_ordinal in contract_local_rows:
        if local_id in locals_by_id or local_id < 0 or source_local_id < 0 or contract_kind not in {1, 2} or clause_ordinal < 0:
            raise NativeWholeFunctionMirError("invalid assembled contract local")
        locals_by_id[local_id] = MirLocal(local_id, f"_contract_{contract_kind}_{source_local_id}", resolved_type(local_type, "contract local"))

    if sorted(locals_by_id) != list(range(len(locals_by_id))):
        raise NativeWholeFunctionMirError("assembled local IDs must be dense")

    contract_by_id: dict[int, tuple[int, ...]] = {}
    for row in contracts:
        kind, clause, contract_kind, start, length, rid, result, left, right, symbol, type_code, policy = row
        if kind >= 2:
            if rid in contract_by_id:
                raise NativeWholeFunctionMirError("duplicate contract instruction ID")
            contract_by_id[rid] = row

    global_instructions: dict[int, MirInstruction] = {}
    expected_global = 0
    for global_id, source_kind, source_id, contract_kind, clause, result, left, right in sources:
        if global_id != expected_global:
            raise NativeWholeFunctionMirError("assembled instruction IDs must be dense and ordered")
        if source_kind == 2:
            try:
                original = body_instructions[source_id]
            except KeyError as error:
                raise NativeWholeFunctionMirError(f"unknown body instruction {source_id}") from error
            global_instructions[global_id] = MirInstruction(
                global_id, original.kind, result=original.result, operands=original.operands,
                symbol=original.symbol, value=original.value, span=original.span,
                ownership=original.ownership, numeric_policy=original.numeric_policy,
                conversion_policy=original.conversion_policy,
            )
        elif source_kind == 1:
            try:
                row = contract_by_id[source_id]
            except KeyError as error:
                raise NativeWholeFunctionMirError(f"unknown contract instruction {source_id}") from error
            kind, _, row_contract_kind, start, length, _, _, _, _, symbol_code, type_code, policy_code = row
            if row_contract_kind != contract_kind or contract_kind not in {1, 2}:
                raise NativeWholeFunctionMirError("contract provenance disagrees with contract record")
            instruction_span = span(start, length, "contract instruction")
            contract_name = "precondition" if contract_kind == 1 else "postcondition"
            if kind == 2:
                literal = source[instruction_span.start:instruction_span.start + instruction_span.length]
                if type_code == 2:
                    value: object = literal == "true"
                    if literal not in {"true", "false"}:
                        raise NativeWholeFunctionMirError("bool contract constant must be true/false")
                else:
                    value = int(literal)
                global_instructions[global_id] = MirInstruction(global_id, "const", result=result, value=value, span=instruction_span, ownership="value")
            elif kind == 3:
                try:
                    op = _SYMBOLS[symbol_code]
                    numeric_policy = _POLICIES[policy_code]
                except KeyError as error:
                    raise NativeWholeFunctionMirError("contract binary has invalid operator/policy") from error
                global_instructions[global_id] = MirInstruction(global_id, "binary", result=result, operands=(left, right), symbol=op, span=instruction_span, numeric_policy=numeric_policy)
            elif kind == 4:
                global_instructions[global_id] = MirInstruction(global_id, "contract_check", operands=(left,), span=instruction_span, contract_kind=contract_name)
            else:
                raise NativeWholeFunctionMirError(f"unsupported contract instruction kind {kind}")
        else:
            raise NativeWholeFunctionMirError(f"unknown instruction source kind {source_kind}")
        expected_global += 1

    placements_by_block: dict[int, list[tuple[int, int]]] = defaultdict(list)
    seen_instruction: set[int] = set()
    for block_id, instruction_id, local_ordinal in placement_rows:
        if instruction_id not in global_instructions or instruction_id in seen_instruction or block_id < 0 or local_ordinal < 0:
            raise NativeWholeFunctionMirError("invalid instruction placement")
        placements_by_block[block_id].append((local_ordinal, instruction_id))
        seen_instruction.add(instruction_id)
    if seen_instruction != set(global_instructions):
        raise NativeWholeFunctionMirError("every assembled instruction must have exactly one placement")
    for rows in placements_by_block.values():
        rows.sort()
        if [ordinal for ordinal, _ in rows] != list(range(len(rows))):
            raise NativeWholeFunctionMirError("block-local placement ordinals must be dense")

    blocks_seen: set[int] = set()
    terminator_rows: dict[int, list[tuple[int, ...]]] = defaultdict(list)
    for row in cfg:
        kind, block_id, operand, target_a, target_b, case_value, ordinal = row
        if kind == 10:
            if block_id in blocks_seen or block_id < 0:
                raise NativeWholeFunctionMirError("duplicate/invalid CFG block")
            blocks_seen.add(block_id)
        else:
            terminator_rows[block_id].append(row)
    if not blocks_seen or 0 not in blocks_seen:
        raise NativeWholeFunctionMirError("CFG must contain entry block zero")

    blocks: list[MirBlock] = []
    for block_id in sorted(blocks_seen):
        rows = terminator_rows.get(block_id, [])
        if not rows:
            raise NativeWholeFunctionMirError(f"block {block_id} has no terminator")
        kinds = {row[0] for row in rows}
        if kinds <= {13, 14}:
            cases = sorted((row for row in rows if row[0] == 13), key=lambda row: row[6])
            defaults = [row for row in rows if row[0] == 14]
            if len(defaults) != 1:
                raise NativeWholeFunctionMirError("switch must contain one default")
            operands = {row[2] for row in rows}
            if len(operands) != 1:
                raise NativeWholeFunctionMirError("switch rows disagree on operand")
            terminator = MirTerminator("switch", operands=(next(iter(operands)),), targets=tuple(row[3] for row in cases) + (defaults[0][3],), cases=tuple(row[5] for row in cases))
        elif len(rows) == 1:
            kind, _, operand, target_a, target_b, _, _ = rows[0]
            if kind == 11:
                terminator = MirTerminator("jump", targets=(target_a,))
            elif kind == 12:
                terminator = MirTerminator("branch", operands=(operand,), targets=(target_a, target_b))
            elif kind == 15:
                terminator = MirTerminator("return", operands=() if operand < 0 else (operand,))
            elif kind == 16:
                terminator = MirTerminator("unreachable")
            else:
                raise NativeWholeFunctionMirError(f"unsupported CFG terminator kind {kind}")
        else:
            raise NativeWholeFunctionMirError(f"block {block_id} has conflicting terminators")
        instructions = tuple(global_instructions[instruction_id] for _, instruction_id in placements_by_block.get(block_id, []))
        blocks.append(MirBlock(block_id, instructions, terminator))

    # Structured lowering may reserve a join before it knows that every branch
    # terminates. Canonical MIR, like the reference compiler's MIR, contains
    # reachable blocks only. Prune those reserved joins before constructing the
    # validated function rather than treating an implementation detail as a
    # second semantic path.
    blocks_by_id = {block.block_id: block for block in blocks}
    reachable: set[int] = set()
    pending = [0]
    while pending:
        block_id = pending.pop()
        if block_id in reachable:
            continue
        block = blocks_by_id.get(block_id)
        if block is None:
            raise NativeWholeFunctionMirError(f"CFG targets unknown block {block_id}")
        reachable.add(block_id)
        pending.extend(block.terminator.targets)
    blocks = [block for block in blocks if block.block_id in reachable]

    resolved_capabilities: list[str] = []
    for raw_id in capability_ids:
        capability_id = int(raw_id)
        try:
            name = capability_names[capability_id]
        except KeyError as error:
            raise NativeWholeFunctionMirError(f"unresolved capability identity {capability_id}") from error
        if not name or name in resolved_capabilities:
            raise NativeWholeFunctionMirError("capability identities must resolve uniquely")
        resolved_capabilities.append(name)

    function = MirFunction(
        function_name,
        return_type,
        tuple(locals_by_id[index] for index in range(len(locals_by_id))),
        tuple(blocks),
        0,
        tuple(resolved_capabilities),
    )
    return MirModule(module_name, (function,))
