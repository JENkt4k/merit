"""Ownership transfer and cleanup planning for bootstrap MIR ABI.

This module is a fail-closed semantic pass between validated MIR ABI and C
emission. It tracks owned locals through calls and acyclic control flow,
requires identical ownership states at joins, and produces deterministic
cleanup actions for every return edge.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature
from merit.bootstrap.mir_contract import MirBlock, MirFunction, MirInstruction

OWNERSHIP_PLAN_SCHEMA = "bootstrap-mir-ownership-v1"
TRANSFER_MODES = frozenset({"copy", "move", "borrow", "mutable_borrow"})


class MirOwnershipError(ValueError):
    """Raised when MIR ownership cannot be proven safe by this pass."""


@dataclass(frozen=True, slots=True)
class CallArgumentTransfer:
    instruction_id: int
    argument_index: int
    local_id: int
    mode: str

    def __post_init__(self) -> None:
        if self.instruction_id < 0 or self.argument_index < 0 or self.local_id < 0:
            raise MirOwnershipError("call transfer identifiers must be non-negative")
        if self.mode not in TRANSFER_MODES:
            raise MirOwnershipError(f"unknown call transfer mode: {self.mode}")

    def to_data(self) -> dict[str, object]:
        return {
            "instruction_id": self.instruction_id,
            "argument_index": self.argument_index,
            "local_id": self.local_id,
            "mode": self.mode,
        }


@dataclass(frozen=True, slots=True)
class CleanupAction:
    block_id: int
    local_id: int
    order: int

    def __post_init__(self) -> None:
        if self.block_id < 0 or self.local_id < 0 or self.order < 0:
            raise MirOwnershipError("cleanup identifiers must be non-negative")

    def to_data(self) -> dict[str, int]:
        return {"block_id": self.block_id, "local_id": self.local_id, "order": self.order}


@dataclass(frozen=True, slots=True)
class FunctionOwnershipPlan:
    function: str
    call_transfers: tuple[CallArgumentTransfer, ...]
    cleanup_actions: tuple[CleanupAction, ...]
    exit_live_owned: tuple[tuple[int, tuple[int, ...]], ...]

    def __post_init__(self) -> None:
        if not self.function:
            raise MirOwnershipError("ownership plan function names must be non-empty")
        transfer_keys = [(item.instruction_id, item.argument_index) for item in self.call_transfers]
        if len(transfer_keys) != len(set(transfer_keys)):
            raise MirOwnershipError("duplicate call transfer entry")
        cleanup_keys = [(item.block_id, item.local_id) for item in self.cleanup_actions]
        if len(cleanup_keys) != len(set(cleanup_keys)):
            raise MirOwnershipError("duplicate cleanup action")

    def to_data(self) -> dict[str, object]:
        return {
            "function": self.function,
            "call_transfers": [item.to_data() for item in self.call_transfers],
            "cleanup_actions": [item.to_data() for item in self.cleanup_actions],
            "exit_live_owned": [
                {"block_id": block_id, "locals": list(locals_)}
                for block_id, locals_ in self.exit_live_owned
            ],
        }


@dataclass(frozen=True, slots=True)
class OwnershipPlan:
    functions: tuple[FunctionOwnershipPlan, ...]
    schema: str = OWNERSHIP_PLAN_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != OWNERSHIP_PLAN_SCHEMA:
            raise MirOwnershipError(f"expected ownership schema {OWNERSHIP_PLAN_SCHEMA!r}")
        names = [function.function for function in self.functions]
        if len(names) != len(set(names)):
            raise MirOwnershipError("duplicate function ownership plan")

    def to_data(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "functions": [function.to_data() for function in self.functions],
        }


def canonical_ownership_json(plan: OwnershipPlan) -> str:
    return json.dumps(plan.to_data(), sort_keys=True, separators=(",", ":"))


def _successors(block: MirBlock) -> tuple[int, ...]:
    return block.terminator.targets


def _topological_blocks(function: MirFunction) -> tuple[MirBlock, ...]:
    """Return deterministic topological order, rejecting cycles for this phase."""

    by_id = {block.block_id: block for block in function.blocks}
    state: dict[int, int] = {}
    ordered: list[int] = []

    def visit(block_id: int) -> None:
        marker = state.get(block_id, 0)
        if marker == 1:
            raise MirOwnershipError(
                f"function {function.name} contains a control-flow cycle; loop cleanup is deferred"
            )
        if marker == 2:
            return
        state[block_id] = 1
        for target in _successors(by_id[block_id]):
            visit(target)
        state[block_id] = 2
        ordered.append(block_id)

    visit(function.entry_block)
    ordered.reverse()
    return tuple(by_id[block_id] for block_id in ordered)


def _parameter_mode(ownership: str) -> str:
    if ownership == "owned":
        return "move"
    if ownership == "borrowed":
        return "borrow"
    if ownership == "mutable_borrow":
        return "mutable_borrow"
    return "copy"


def _require_live(function: str, instruction: int, local_id: int, live: set[int]) -> None:
    if local_id not in live:
        raise MirOwnershipError(
            f"function {function} instruction {instruction} uses non-live owned local {local_id}"
        )


def _apply_instruction(
    function: MirFunction,
    instruction: MirInstruction,
    live: set[int],
    owned_locals: set[int],
    signatures: Mapping[str, MirFunctionSignature],
    transfers: list[CallArgumentTransfer],
) -> None:
    owned_operands = [operand for operand in instruction.operands if operand in owned_locals]

    if instruction.kind == "copy" and instruction.result in owned_locals:
        raise MirOwnershipError(
            f"function {function.name} instruction {instruction.instruction_id} copies into owned local"
        )
    if instruction.kind == "move":
        if len(instruction.operands) != 1:
            raise MirOwnershipError("move instructions require exactly one operand")
        source = instruction.operands[0]
        if source in owned_locals:
            _require_live(function.name, instruction.instruction_id, source, live)
            live.remove(source)
        if instruction.result in owned_locals:
            live.add(instruction.result)
        return
    if instruction.kind in {"drop", "deallocate"}:
        for operand in owned_operands:
            _require_live(function.name, instruction.instruction_id, operand, live)
            live.remove(operand)
        return
    if instruction.kind == "borrow":
        for operand in owned_operands:
            _require_live(function.name, instruction.instruction_id, operand, live)
        return
    if instruction.kind == "call":
        if not instruction.symbol or instruction.symbol not in signatures:
            raise MirOwnershipError(
                f"function {function.name} call {instruction.instruction_id} has unknown signature"
            )
        signature = signatures[instruction.symbol]
        if len(signature.parameters) != len(instruction.operands):
            raise MirOwnershipError(
                f"function {function.name} call {instruction.instruction_id} arity disagrees with ABI"
            )
        for index, (operand, parameter) in enumerate(zip(instruction.operands, signature.parameters)):
            mode = _parameter_mode(parameter.ownership)
            transfers.append(CallArgumentTransfer(instruction.instruction_id, index, operand, mode))
            if operand in owned_locals:
                _require_live(function.name, instruction.instruction_id, operand, live)
                if mode == "move":
                    live.remove(operand)
            elif mode in {"move", "borrow", "mutable_borrow"}:
                raise MirOwnershipError(
                    f"function {function.name} call {instruction.instruction_id} argument {index} "
                    f"requires {mode} ownership but local {operand} is not owned"
                )
        if instruction.result in owned_locals:
            live.add(instruction.result)
        return

    for operand in owned_operands:
        _require_live(function.name, instruction.instruction_id, operand, live)
    if instruction.result in owned_locals and instruction.kind in {
        "const", "construct", "allocate", "convert", "binary"
    }:
        if instruction.result in live:
            raise MirOwnershipError(
                f"function {function.name} instruction {instruction.instruction_id} overwrites live owned local"
            )
        live.add(instruction.result)


def _analyze_function(
    function: MirFunction,
    own_signature: MirFunctionSignature,
    signatures: Mapping[str, MirFunctionSignature],
) -> FunctionOwnershipPlan:
    blocks = _topological_blocks(function)
    predecessors: dict[int, list[int]] = {block.block_id: [] for block in blocks}
    by_id = {block.block_id: block for block in blocks}
    for block in blocks:
        for target in block.terminator.targets:
            predecessors[target].append(block.block_id)

    owned_locals = {local.local_id for local in function.locals if local.ownership == "owned"}
    parameter_owned = {
        parameter.local_id for parameter in own_signature.parameters if parameter.ownership == "owned"
    }
    in_state: dict[int, frozenset[int]] = {function.entry_block: frozenset(parameter_owned)}
    out_state: dict[int, frozenset[int]] = {}
    transfers: list[CallArgumentTransfer] = []
    cleanup: list[CleanupAction] = []
    exits: list[tuple[int, tuple[int, ...]]] = []

    for block in blocks:
        if block.block_id != function.entry_block:
            incoming = [out_state[pred] for pred in predecessors[block.block_id] if pred in out_state]
            if not incoming:
                raise MirOwnershipError(f"missing ownership predecessor state for block {block.block_id}")
            if any(state != incoming[0] for state in incoming[1:]):
                raise MirOwnershipError(
                    f"function {function.name} block {block.block_id} joins inconsistent ownership states"
                )
            in_state[block.block_id] = incoming[0]
        live = set(in_state[block.block_id])
        for instruction in block.instructions:
            _apply_instruction(function, instruction, live, owned_locals, signatures, transfers)

        if block.terminator.kind == "return":
            returned_owned = {
                operand for operand in block.terminator.operands if operand in owned_locals
            }
            for operand in returned_owned:
                _require_live(function.name, -1, operand, live)
                live.remove(operand)
            ordered_cleanup = tuple(sorted(live, reverse=True))
            exits.append((block.block_id, ordered_cleanup))
            for order, local_id in enumerate(ordered_cleanup):
                cleanup.append(CleanupAction(block.block_id, local_id, order))
            live.clear()
        out_state[block.block_id] = frozenset(live)

    return FunctionOwnershipPlan(
        function.name,
        tuple(sorted(transfers, key=lambda item: (item.instruction_id, item.argument_index))),
        tuple(sorted(cleanup, key=lambda item: (item.block_id, item.order))),
        tuple(sorted(exits)),
    )


def analyze_ownership(abi: MirAbiModule) -> OwnershipPlan:
    """Validate call transfers and derive deterministic return cleanup plans."""

    signatures = abi.signature_map()
    functions = tuple(
        _analyze_function(function, signatures[function.name], signatures)
        for function in abi.module.functions
    )
    return OwnershipPlan(functions)
