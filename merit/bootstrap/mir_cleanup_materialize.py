"""Materialize ownership cleanup as explicit typed MIR drop instructions.

This pass consumes validated ``bootstrap-mir-abi-v1`` plus the ownership proof
from ``bootstrap-mir-ownership-v1``.  It rewrites explicit drop/deallocate
sites with stable destructor symbols and appends implicit return-edge cleanup as
ordinary MIR ``drop`` instructions.  Instruction IDs are then renumbered in
stable function/block/source order.
"""

from __future__ import annotations

from dataclasses import replace

from merit.bootstrap.mir_abi import MirAbiModule
from merit.bootstrap.mir_cleanup_to_c import CleanupCPolicy, MirCleanupToCError
from merit.bootstrap.mir_contract import MirBlock, MirFunction, MirInstruction, MirModule, MirType
from merit.bootstrap.mir_ownership import OwnershipPlan, analyze_ownership, canonical_ownership_json

MATERIALIZED_CLEANUP_SCHEMA = "bootstrap-mir-cleanup-v1"


class MirCleanupMaterializationError(MirCleanupToCError):
    """Raised when an ownership plan cannot become explicit MIR cleanup."""


def _validate_plan(abi: MirAbiModule, supplied: OwnershipPlan | None) -> OwnershipPlan:
    expected = analyze_ownership(abi)
    if supplied is None:
        return expected
    if canonical_ownership_json(supplied) != canonical_ownership_json(expected):
        raise MirCleanupMaterializationError("supplied ownership plan is stale or does not match MIR")
    return supplied


def _destructor_map(policy: CleanupCPolicy) -> dict[MirType, str]:
    return policy.destructor_map()


def _required_types(abi: MirAbiModule, plan: OwnershipPlan) -> set[MirType]:
    required: set[MirType] = set()
    plan_by_name = {item.function: item for item in plan.functions}
    for function in abi.module.functions:
        locals_ = {local.local_id: local for local in function.locals}
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.kind not in {"drop", "deallocate"}:
                    continue
                if len(instruction.operands) != 1:
                    raise MirCleanupMaterializationError(
                        f"{instruction.kind} instruction {instruction.instruction_id} requires one operand"
                    )
                local = locals_[instruction.operands[0]]
                if local.ownership != "owned":
                    raise MirCleanupMaterializationError(
                        f"{instruction.kind} instruction {instruction.instruction_id} targets non-owned local"
                    )
                required.add(local.type)
        function_plan = plan_by_name[function.name]
        for action in function_plan.cleanup_actions:
            local = locals_.get(action.local_id)
            if local is None or local.ownership != "owned":
                raise MirCleanupMaterializationError("ownership cleanup references invalid owned local")
            required.add(local.type)
    return required


def _validate_destructors(abi: MirAbiModule, plan: OwnershipPlan, policy: CleanupCPolicy) -> dict[MirType, str]:
    destructors = _destructor_map(policy)
    required = _required_types(abi, plan)
    missing = sorted(type_.name for type_ in required if type_ not in destructors)
    if missing:
        raise MirCleanupMaterializationError(f"missing destructor bindings for owned types: {missing}")
    emitted = {signature.exported_name or signature.function for signature in abi.signatures}
    collisions = sorted(symbol for symbol in destructors.values() if symbol in emitted)
    if collisions:
        raise MirCleanupMaterializationError(f"destructor symbols collide with emitted functions: {collisions}")
    return destructors


def _copy_instruction(instruction: MirInstruction, instruction_id: int, *, symbol: str | None = None) -> MirInstruction:
    return MirInstruction(
        instruction_id,
        instruction.kind,
        result=instruction.result,
        operands=instruction.operands,
        symbol=instruction.symbol if symbol is None else symbol,
        value=instruction.value,
        span=instruction.span,
        ownership=instruction.ownership,
        numeric_policy=instruction.numeric_policy,
        conversion_policy=instruction.conversion_policy,
        contract_kind=instruction.contract_kind,
        capabilities=instruction.capabilities,
    )


def _materialize_function(function: MirFunction, function_plan, destructors: dict[MirType, str]) -> MirFunction:
    locals_ = {local.local_id: local for local in function.locals}
    cleanup_by_block: dict[int, list[object]] = {}
    for action in function_plan.cleanup_actions:
        cleanup_by_block.setdefault(action.block_id, []).append(action)

    next_id = 0
    blocks: list[MirBlock] = []
    for block in function.blocks:
        instructions: list[MirInstruction] = []
        for instruction in block.instructions:
            symbol = None
            if instruction.kind in {"drop", "deallocate"}:
                local = locals_[instruction.operands[0]]
                symbol = destructors[local.type]
            instructions.append(_copy_instruction(instruction, next_id, symbol=symbol))
            next_id += 1
        if block.terminator.kind == "return":
            actions = sorted(cleanup_by_block.get(block.block_id, ()), key=lambda item: item.order)
            for action in actions:
                local = locals_[action.local_id]
                instructions.append(MirInstruction(
                    next_id,
                    "drop",
                    operands=(action.local_id,),
                    symbol=destructors[local.type],
                    span=block.terminator.span,
                    ownership="owned",
                ))
                next_id += 1
        blocks.append(MirBlock(block.block_id, tuple(instructions), block.terminator))
    return MirFunction(
        function.name,
        function.return_type,
        function.locals,
        tuple(blocks),
        function.entry_block,
        function.capabilities,
    )


def materialize_cleanup_mir(
    abi: MirAbiModule,
    policy: CleanupCPolicy,
    *,
    ownership_plan: OwnershipPlan | None = None,
) -> MirAbiModule:
    """Return ABI-equivalent MIR with every supported cleanup operation explicit."""

    plan = _validate_plan(abi, ownership_plan)
    destructors = _validate_destructors(abi, plan, policy)
    plans = {item.function: item for item in plan.functions}
    functions = tuple(
        _materialize_function(function, plans[function.name], destructors)
        for function in abi.module.functions
    )
    return MirAbiModule(MirModule(abi.module.name, functions), abi.signatures)
