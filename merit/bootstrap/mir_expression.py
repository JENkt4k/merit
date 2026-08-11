"""Expression-scoped bridge from checked HIR into canonical ``bootstrap-mir-v1``.

The repository expression corpus models semantic values rather than complete
functions. MIR is function-scoped, so this adapter wraps one checked expression
root in a synthetic return/function envelope and delegates all operational
lowering to the existing HIR-to-MIR implementation.
"""

from __future__ import annotations

from merit.bootstrap.hir_contract import HirModule, HirNode
from merit.bootstrap.hir_to_mir import HirToMirError, lower_hir_to_mir
from merit.bootstrap.mir_contract import MirModule


class ExpressionMirLoweringError(HirToMirError):
    """Raised when expression HIR cannot form the MIR parity envelope."""


def lower_expression_hir_to_mir(expression: HirModule) -> MirModule:
    """Lower exactly one checked expression root into a synthetic MIR function.

    Existing HIR node IDs and bindings are preserved. Two envelope nodes are
    appended after the expression graph so temporary names and source-binding
    local identities remain exactly those produced by the normal MIR lowerer.
    """

    if len(expression.roots) != 1:
        raise ExpressionMirLoweringError(
            f"expression MIR parity requires exactly one HIR root, got {len(expression.roots)}"
        )
    by_id = {node.node_id: node for node in expression.nodes}
    root_id = expression.roots[0]
    try:
        root = by_id[root_id]
    except KeyError as error:
        raise ExpressionMirLoweringError(
            f"expression HIR root {root_id} does not exist"
        ) from error
    if root.kind in {
        "function", "block", "let", "assign", "drop", "contract_check",
        "capability_scope", "return", "if", "while", "match", "match_arm",
        "parameter",
    }:
        raise ExpressionMirLoweringError(
            f"expression MIR root must be a value, found {root.kind!r}"
        )
    next_id = max(by_id, default=-1) + 1
    return_node = HirNode(next_id, "return", root.type, children=(root_id,))
    function_node = HirNode(
        next_id + 1,
        "function",
        root.type,
        children=(return_node.node_id,),
        symbol=expression.name,
    )
    wrapped = HirModule(
        expression.name,
        expression.bindings,
        expression.nodes + (return_node, function_node),
        (function_node.node_id,),
        expression.schema,
    )
    return lower_hir_to_mir(wrapped)
