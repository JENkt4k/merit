"""Materialize ownership-aware native function assembly as bootstrap-mir-v1.

This adapter extends the existing whole-function assembly boundary without
re-running source or ownership analysis.  Native source_kind=3 provenance is
resolved from validated MirOwnershipRecord rows and inserted back into the CFG
as explicit move/drop instructions after the source/contract records have been
materialized by the existing adapter.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from merit.bootstrap.mir_contract import MirBlock, MirFunction, MirInstruction, MirLocal, MirModule, MirType
from merit.bootstrap.mir_function_assembly_parity import (
    NativeWholeFunctionMirError,
    lower_native_whole_function_assembly,
)

OwnershipBindingRecord = tuple[int, int, int, int]
OwnershipRecord = tuple[int, int, int, int, int, int, int, int]
InstructionSourceRecord = tuple[int, ...]
PlacementRecord = tuple[int, ...]


def _rows(values: Iterable[tuple[int, ...]], width: int, label: str) -> tuple[tuple[int, ...], ...]:
    rows = tuple(tuple(int(value) for value in row) for row in values)
    for index, row in enumerate(rows):
        if len(row) != width:
            raise NativeWholeFunctionMirError(f"{label} record {index} must contain {width} fields")
    return rows


def _copy_instruction(instruction: MirInstruction, instruction_id: int) -> MirInstruction:
    return MirInstruction(
        instruction_id,
        instruction.kind,
        result=instruction.result,
        operands=instruction.operands,
        symbol=instruction.symbol,
        value=instruction.value,
        span=instruction.span,
        ownership=instruction.ownership,
        numeric_policy=instruction.numeric_policy,
        conversion_policy=instruction.conversion_policy,
        contract_kind=instruction.contract_kind,
        capabilities=instruction.capabilities,
        specialization=instruction.specialization,
    )


def lower_native_ownership_whole_function_assembly(
    *,
    source: str,
    module_name: str,
    body_records: Iterable[tuple[int, ...]],
    contract_records: Iterable[tuple[int, ...]],
    contract_locals: Iterable[tuple[int, ...]],
    instruction_sources: Iterable[InstructionSourceRecord],
    ownership_bindings: Iterable[OwnershipBindingRecord],
    ownership_records: Iterable[OwnershipRecord],
    cfg_records: Iterable[tuple[int, ...]],
    placements: Iterable[PlacementRecord],
    capability_ids: Iterable[int],
    capability_names: Mapping[int, str],
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    """Materialize one ownership-aware native function into canonical MIR."""

    sources = _rows(instruction_sources, 8, "instruction source")
    binding_rows = _rows(ownership_bindings, 4, "ownership binding")
    ownership_rows = _rows(ownership_records, 8, "ownership")
    placement_rows = _rows(placements, 3, "placement")

    if [row[0] for row in sources] != list(range(len(sources))):
        raise NativeWholeFunctionMirError("assembled instruction IDs must be dense and ordered")

    old_to_reduced: dict[int, int] = {}
    reduced_sources: list[tuple[int, ...]] = []
    for row in sources:
        global_id, source_kind, source_id, contract_kind, clause, result, left, right = row
        if source_kind in {1, 2}:
            reduced_id = len(reduced_sources)
            old_to_reduced[global_id] = reduced_id
            reduced_sources.append((reduced_id, source_kind, source_id, contract_kind, clause, result, left, right))
        elif source_kind != 3:
            raise NativeWholeFunctionMirError(f"unknown instruction source kind {source_kind}")

    reduced_ordinals: dict[int, int] = defaultdict(int)
    reduced_placements: list[tuple[int, int, int]] = []
    original_by_block: dict[int, list[tuple[int, int]]] = defaultdict(list)
    seen_global: set[int] = set()
    for block_id, instruction_id, local_ordinal in placement_rows:
        if instruction_id < 0 or instruction_id >= len(sources) or instruction_id in seen_global:
            raise NativeWholeFunctionMirError("invalid instruction placement")
        if block_id < 0 or local_ordinal < 0:
            raise NativeWholeFunctionMirError("invalid instruction placement")
        seen_global.add(instruction_id)
        original_by_block[block_id].append((local_ordinal, instruction_id))
        reduced_id = old_to_reduced.get(instruction_id)
        if reduced_id is not None:
            ordinal = reduced_ordinals[block_id]
            reduced_placements.append((block_id, reduced_id, ordinal))
            reduced_ordinals[block_id] = ordinal + 1
    if seen_global != set(range(len(sources))):
        raise NativeWholeFunctionMirError("every assembled instruction must have exactly one placement")
    for rows in original_by_block.values():
        rows.sort()
        if [ordinal for ordinal, _ in rows] != list(range(len(rows))):
            raise NativeWholeFunctionMirError("block-local placement ordinals must be dense")

    base = lower_native_whole_function_assembly(
        source=source,
        module_name=module_name,
        body_records=body_records,
        contract_records=contract_records,
        contract_locals=contract_locals,
        instruction_sources=reduced_sources,
        cfg_records=cfg_records,
        placements=reduced_placements,
        capability_ids=capability_ids,
        capability_names=capability_names,
        type_names=type_names,
    )
    if len(base.functions) != 1:
        raise NativeWholeFunctionMirError("ownership assembly expects exactly one function")
    function = base.functions[0]

    binding_by_local: dict[int, tuple[int, int, int, int]] = {}
    for binding_id, local_id, owned, mutable in binding_rows:
        if binding_id < 0 or local_id < 0 or owned not in {0, 1} or mutable not in {0, 1}:
            raise NativeWholeFunctionMirError("invalid ownership binding")
        if local_id in binding_by_local:
            raise NativeWholeFunctionMirError("duplicate ownership local")
        binding_by_local[local_id] = (binding_id, local_id, owned, mutable)

    locals_: list[MirLocal] = []
    for local in function.locals:
        binding = binding_by_local.get(local.local_id)
        if binding is None:
            locals_.append(local)
            continue
        binding_id, _, owned, mutable = binding
        if local.source_binding_id is not None and local.source_binding_id != binding_id:
            raise NativeWholeFunctionMirError("ownership binding disagrees with body local identity")
        locals_.append(MirLocal(
            local.local_id,
            local.name,
            local.type,
            mutable=bool(mutable),
            ownership="owned" if owned else local.ownership,
            source_binding_id=binding_id,
        ))

    reduced_instruction: dict[int, MirInstruction] = {}
    for block in function.blocks:
        for instruction in block.instructions:
            reduced_instruction[instruction.instruction_id] = instruction

    final_instruction: dict[int, MirInstruction] = {}
    for row in sources:
        global_id, source_kind, source_id, _, _, result, left, _ = row
        if source_kind in {1, 2}:
            reduced_id = old_to_reduced[global_id]
            try:
                final_instruction[global_id] = _copy_instruction(reduced_instruction[reduced_id], global_id)
            except KeyError as error:
                raise NativeWholeFunctionMirError("reduced instruction provenance is incomplete") from error
            continue

        if source_id < 0 or source_id >= len(ownership_rows):
            raise NativeWholeFunctionMirError("ownership provenance references unknown record")
        record = ownership_rows[source_id]
        record_kind, instruction_id, _, _, operand_local, _, _, _ = record
        if instruction_id < 0:
            raise NativeWholeFunctionMirError("ownership provenance references non-instruction record")
        if left != operand_local or left < 0:
            raise NativeWholeFunctionMirError("ownership provenance disagrees with operand local")
        if record_kind in {2, 5}:
            if result < 0:
                raise NativeWholeFunctionMirError("ownership move requires destination local")
            final_instruction[global_id] = MirInstruction(
                global_id, "move", result=result, operands=(left,), ownership="owned"
            )
        elif record_kind in {3, 4, 6}:
            if result != -1:
                raise NativeWholeFunctionMirError("ownership drop cannot produce a result")
            final_instruction[global_id] = MirInstruction(
                global_id, "drop", operands=(left,), ownership="owned"
            )
        else:
            raise NativeWholeFunctionMirError(f"unsupported ownership instruction kind {record_kind}")

    blocks: list[MirBlock] = []
    base_by_id = {block.block_id: block for block in function.blocks}
    for block_id in sorted(base_by_id):
        block = base_by_id[block_id]
        rows = original_by_block.get(block_id, [])
        instructions = tuple(final_instruction[instruction_id] for _, instruction_id in rows)
        blocks.append(MirBlock(block_id, instructions, block.terminator))

    return MirModule(module_name, (MirFunction(
        function.name,
        function.return_type,
        tuple(locals_),
        tuple(blocks),
        function.entry_block,
        function.capabilities,
        function.parameters,
        function.return_mode,
        function.borrowed_origin,
    ),))
