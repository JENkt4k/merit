"""Primitive typed-expression lowering into ``bootstrap-hir-v1``.

This is the first executable AST->HIR slice. It intentionally accepts an
explicit expected type supplied by the typed-expression boundary instead of
performing name resolution or type inference itself.
"""

from __future__ import annotations

from .ast_contract import AstNode
from .hir_contract import HirModule, HirNode, HirType, SourceSpan


_BINARY_SYMBOLS = {
    "add": "+",
    "subtract": "-",
    "multiply": "*",
    "divide": "/",
}


class PrimitiveHirLoweringError(ValueError):
    """Raised when an AST node is outside the first typed HIR slice."""


def _span(node: AstNode) -> SourceSpan:
    return SourceSpan(node.start, node.length)


def lower_primitive_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    module_name: str = "expression",
) -> HirModule:
    """Lower exact numeric literals and primitive arithmetic to typed HIR.

    The caller supplies the already-resolved destination type. This mirrors
    Merit's destination-typing rule without making this bootstrap layer a type
    inference engine. Primitive integer arithmetic is represented as checked;
    numeric literals remain exact source values.
    """

    if not module_name:
        raise PrimitiveHirLoweringError("module name must be non-empty")
    if node.start < 0 or node.length < 0 or node.start + node.length > len(source):
        raise PrimitiveHirLoweringError("AST span is outside source text")

    nodes: list[HirNode] = []

    def lower(current: AstNode) -> int:
        if current.start < 0 or current.length < 0 or current.start + current.length > len(source):
            raise PrimitiveHirLoweringError("AST span is outside source text")

        if current.kind == "exact_numeric":
            if current.children:
                raise PrimitiveHirLoweringError("numeric literal unexpectedly has children")
            value = source[current.start : current.start + current.length]
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "literal",
                    expected_type,
                    span=_span(current),
                    value=value,
                    numeric_policy="exact",
                )
            )
            return node_id

        symbol = _BINARY_SYMBOLS.get(current.kind)
        if symbol is not None:
            if len(current.children) != 2:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} requires exactly two AST children"
                )
            left = lower(current.children[0])
            right = lower(current.children[1])
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "binary",
                    expected_type,
                    children=(left, right),
                    span=_span(current),
                    symbol=symbol,
                    numeric_policy="checked",
                )
            )
            return node_id

        raise PrimitiveHirLoweringError(
            f"AST kind {current.kind!r} is outside primitive HIR v1"
        )

    root = lower(node)
    return HirModule(module_name, (), tuple(nodes), (root,))
