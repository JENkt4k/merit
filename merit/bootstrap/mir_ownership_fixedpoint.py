"""Loop-aware ownership analysis for validated bootstrap MIR ABI.

This pass extends ``bootstrap-mir-ownership-v1`` to cyclic control flow.  It
uses an exact finite-state fixed point: every block has one incoming set of live
owned locals, and every predecessor must agree on that set.  Back edges are
therefore accepted only when an iteration preserves the loop header ownership
state.  Ownership-changing cycles fail closed until richer loop-carried value
semantics are specified.
"""

from __future__ import annotations

from collections import deque

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature
from merit.bootstrap.mir_ownership import (
    CallArgumentTransfer,
    CleanupAction,
    FunctionOwnershipPlan,
    MirOwnershipError,
    OwnershipPlan,
    _apply_instruction,
)

LOOP_OWNERSHIP_SCHEMA = "bootstrap-mir-ownership-v2"


def _successors(block):
    return block.terminator.targets


def _analyze_function_fixedpoint(function, own_signature, signatures):
    by_id = {block.block_id: block for block in function.blocks}
    owned_locals = {local.local_id for local in function.locals if local.ownership == "owned"}
    parameter_owned = frozenset(
        parameter.local_id
        for parameter in own_signature.parameters
        if parameter.ownership == "owned"
    )

    incoming: dict[int, frozenset[int]] = {function.entry_block: parameter_owned}
    outgoing: dict[int, frozenset[int]] = {}
    processed: set[int] = set()
    queue = deque([function.entry_block])
    transfers: dict[tuple[int, int], CallArgumentTransfer] = {}
    cleanup: dict[tuple[int, int], CleanupAction] = {}
    exits: dict[int, tuple[int, ...]] = {}

    while queue:
        block_id = queue.popleft()
        state = incoming[block_id]
        if block_id in processed:
            # A repeated block with the same state is the fixed point.  A
            # different state is rejected when the edge is propagated below.
            continue
        processed.add(block_id)
        block = by_id[block_id]
        live = set(state)
        block_transfers: list[CallArgumentTransfer] = []
        for instruction in block.instructions:
            _apply_instruction(
                function,
                instruction,
                live,
                owned_locals,
                signatures,
                block_transfers,
            )
        for transfer in block_transfers:
            key = (transfer.instruction_id, transfer.argument_index)
            previous = transfers.get(key)
            if previous is not None and previous != transfer:
                raise MirOwnershipError("loop analysis produced inconsistent call transfer")
            transfers[key] = transfer

        if block.terminator.kind == "return":
            for operand in block.terminator.operands:
                if operand in owned_locals:
                    if operand not in live:
                        raise MirOwnershipError(
                            f"function {function.name} returns non-live owned local {operand}"
                        )
                    live.remove(operand)
            ordered = tuple(sorted(live, reverse=True))
            exits[block_id] = ordered
            for order, local_id in enumerate(ordered):
                cleanup[(block_id, local_id)] = CleanupAction(block_id, local_id, order)
            live.clear()

        out = frozenset(live)
        outgoing[block_id] = out
        for target in _successors(block):
            previous = incoming.get(target)
            if previous is None:
                incoming[target] = out
                queue.append(target)
            elif previous != out:
                raise MirOwnershipError(
                    f"function {function.name} block {target} joins inconsistent ownership states "
                    f"{sorted(previous)} and {sorted(out)}"
                )
            elif target not in processed:
                queue.append(target)

    unreachable = sorted(set(by_id) - processed)
    if unreachable:
        raise MirOwnershipError(
            f"function {function.name} has unreachable ownership blocks: {unreachable}"
        )

    return FunctionOwnershipPlan(
        function.name,
        tuple(transfers[key] for key in sorted(transfers)),
        tuple(cleanup[key] for key in sorted(cleanup, key=lambda item: (item[0], cleanup[item].order))),
        tuple((block_id, exits[block_id]) for block_id in sorted(exits)),
    )


def analyze_ownership_fixedpoint(abi: MirAbiModule) -> OwnershipPlan:
    """Analyze ownership over cyclic MIR using exact state convergence.

    The returned object deliberately retains the v1 ownership-plan interchange
    shape so cleanup materialization can consume it unchanged.  The algorithmic
    contract is versioned by this module and documentation rather than by
    weakening existing serialized plans.
    """

    signatures = abi.signature_map()
    return OwnershipPlan(
        tuple(
            _analyze_function_fixedpoint(function, signatures[function.name], signatures)
            for function in abi.module.functions
        )
    )
