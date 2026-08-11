"""Strict adapter for Merit-native whole-function CFG MIR records."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from .mir_contract import MirBlock, MirContractError, MirTerminator


@dataclass(frozen=True, slots=True)
class NativeCfgRecord:
    kind: int
    block_id: int
    operand: int = -1
    target_a: int = -1
    target_b: int = -1
    case_value: int = 0
    ordinal: int = 0


def lower_native_cfg_records(records: Sequence[NativeCfgRecord], *, instructions_by_block=None) -> tuple[MirBlock, ...]:
    """Validate native CFG decisions and reconstruct canonical MIR blocks.

    This adapter never allocates blocks, infers targets, reorders switch cases,
    or synthesizes control flow. Those decisions must be explicit in records.
    """
    instructions_by_block = instructions_by_block or {}
    block_order: list[int] = []
    terminators: dict[int, MirTerminator] = {}
    switches: dict[int, list[NativeCfgRecord]] = {}

    for record in records:
        if record.kind == 10:
            if record.block_id < 0 or record.block_id in block_order:
                raise MirContractError("CFG block IDs must be unique and non-negative")
            if record.ordinal != len(block_order):
                raise MirContractError("CFG block ordinals must be dense and ordered")
            block_order.append(record.block_id)
        elif record.kind == 11:
            _set_terminator(terminators, record.block_id, MirTerminator("jump", targets=(_target(record.target_a),)))
        elif record.kind == 12:
            if record.operand < 0:
                raise MirContractError("CFG branch requires a condition local")
            _set_terminator(terminators, record.block_id, MirTerminator("branch", operands=(record.operand,), targets=(_target(record.target_a), _target(record.target_b))))
        elif record.kind in (13, 14):
            if record.operand < 0:
                raise MirContractError("CFG switch requires a value local")
            switches.setdefault(record.block_id, []).append(record)
        elif record.kind == 15:
            operands = () if record.operand < 0 else (record.operand,)
            _set_terminator(terminators, record.block_id, MirTerminator("return", operands=operands))
        elif record.kind == 16:
            _set_terminator(terminators, record.block_id, MirTerminator("unreachable"))
        else:
            raise MirContractError(f"unknown native CFG record kind: {record.kind}")

    known = set(block_order)
    if not block_order:
        raise MirContractError("native CFG requires at least one block")
    for block_id, group in switches.items():
        if block_id in terminators:
            raise MirContractError("CFG block has multiple terminators")
        ordered = sorted(group, key=lambda item: item.ordinal)
        if [item.ordinal for item in ordered] != list(range(len(ordered))):
            raise MirContractError("CFG switch ordinals must be dense")
        defaults = [item for item in ordered if item.kind == 14]
        cases = [item for item in ordered if item.kind == 13]
        if len(defaults) != 1 or ordered[-1].kind != 14:
            raise MirContractError("CFG switch requires exactly one final default")
        if any(item.operand != ordered[0].operand for item in ordered):
            raise MirContractError("CFG switch records disagree on operand")
        values = [item.case_value for item in cases]
        if len(values) != len(set(values)):
            raise MirContractError("CFG switch contains duplicate cases")
        terminators[block_id] = MirTerminator("switch", operands=(ordered[0].operand,), targets=tuple(_target(item.target_a) for item in cases + defaults), cases=tuple(values))

    if set(terminators) != known:
        missing = sorted(known - set(terminators))
        extra = sorted(set(terminators) - known)
        raise MirContractError(f"CFG terminator/block mismatch: missing={missing}, extra={extra}")
    for terminator in terminators.values():
        if any(target not in known for target in terminator.targets):
            raise MirContractError("CFG terminator references unknown block")
    extra_instruction_blocks = set(instructions_by_block) - known
    if extra_instruction_blocks:
        raise MirContractError("CFG instructions reference unknown block")
    return tuple(MirBlock(block_id, tuple(instructions_by_block.get(block_id, ())), terminators[block_id]) for block_id in block_order)


def _set_terminator(terminators: dict[int, MirTerminator], block_id: int, terminator: MirTerminator) -> None:
    if block_id < 0 or block_id in terminators:
        raise MirContractError("CFG block has invalid or multiple terminators")
    terminators[block_id] = terminator


def _target(value: int) -> int:
    if value < 0:
        raise MirContractError("CFG targets must be non-negative")
    return value
