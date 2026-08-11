"""Strict integration of native CFG topology and native instruction placement.

Expression/instruction semantics and source-local identity are already measured by the
function MIR replacement boundary.  This module measures the next independent
decision: which globally ordered MIR instruction belongs to which native-allocated
basic block.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from .mir_cfg_parity import NativeCfgRecord, lower_native_cfg_records
from .mir_contract import MirBlock, MirContractError, MirFunction, MirInstruction, MirLocal, MirModule, MirType


@dataclass(frozen=True, slots=True)
class NativeInstructionPlacement:
    block_id: int
    instruction_id: int
    ordinal: int


def lower_native_cfg_function(
    *,
    module_name: str,
    function_name: str,
    return_type: MirType,
    locals: Sequence[MirLocal],
    instructions: Sequence[MirInstruction],
    cfg_records: Sequence[NativeCfgRecord],
    placements: Sequence[NativeInstructionPlacement],
    entry_block: int = 0,
    capabilities: Sequence[str] = (),
) -> MirModule:
    """Reconstruct a complete function from independent native CFG decisions.

    The adapter does not infer instruction placement from HIR, source spans, block
    reachability, or instruction kinds.  Every instruction must be assigned exactly
    once by an explicit placement record.  CFG topology is independently validated
    by :func:`lower_native_cfg_records`.
    """
    if not module_name or not function_name:
        raise MirContractError("native CFG function names must be non-empty")
    if entry_block < 0:
        raise MirContractError("native CFG entry block must be non-negative")

    instruction_by_id = {instruction.instruction_id: instruction for instruction in instructions}
    if len(instruction_by_id) != len(instructions):
        raise MirContractError("native CFG instruction IDs must be unique")
    expected_instruction_ids = list(range(len(instructions)))
    if sorted(instruction_by_id) != expected_instruction_ids:
        raise MirContractError("native CFG instruction IDs must be globally dense")

    placed_ids: set[int] = set()
    placements_by_block: dict[int, list[NativeInstructionPlacement]] = {}
    for placement in placements:
        if placement.block_id < 0:
            raise MirContractError("native instruction placement has negative block ID")
        if placement.instruction_id not in instruction_by_id:
            raise MirContractError("native instruction placement references unknown instruction")
        if placement.instruction_id in placed_ids:
            raise MirContractError("native MIR instruction is placed more than once")
        if placement.ordinal < 0:
            raise MirContractError("native instruction placement ordinal must be non-negative")
        placed_ids.add(placement.instruction_id)
        placements_by_block.setdefault(placement.block_id, []).append(placement)

    if placed_ids != set(instruction_by_id):
        missing = sorted(set(instruction_by_id) - placed_ids)
        raise MirContractError(f"native CFG leaves MIR instructions unplaced: {missing}")

    instructions_by_block: dict[int, tuple[MirInstruction, ...]] = {}
    for block_id, group in placements_by_block.items():
        ordered = sorted(group, key=lambda placement: placement.ordinal)
        if [placement.ordinal for placement in ordered] != list(range(len(ordered))):
            raise MirContractError("native block instruction ordinals must be dense")
        ids = [placement.instruction_id for placement in ordered]
        if ids != sorted(ids):
            raise MirContractError("native block instructions must preserve global instruction order")
        instructions_by_block[block_id] = tuple(instruction_by_id[instruction_id] for instruction_id in ids)

    blocks = lower_native_cfg_records(cfg_records, instructions_by_block=instructions_by_block)
    known_blocks = {block.block_id for block in blocks}
    if entry_block not in known_blocks:
        raise MirContractError("native CFG entry block does not exist")

    function = MirFunction(
        function_name,
        return_type,
        tuple(locals),
        tuple(blocks),
        entry_block,
        tuple(capabilities),
    )
    return MirModule(module_name, (function,))


def placement_from_blocks(blocks: Sequence[MirBlock]) -> tuple[NativeInstructionPlacement, ...]:
    """Test/support helper that exposes the placement contract for existing MIR.

    Production parity gates should compare independently emitted native records;
    this helper is intentionally mechanical and never used by the lowering adapter.
    """
    return tuple(
        NativeInstructionPlacement(block.block_id, instruction.instruction_id, ordinal)
        for block in blocks
        for ordinal, instruction in enumerate(block.instructions)
    )
