"""Typed-expression lowering into ``bootstrap-hir-v1``.

The bootstrap HIR boundary is deliberately explicit: callers provide resolved
binding types and the numeric destination type instead of asking this layer to
perform inference. That keeps differential comparison focused on semantic
lowering rather than recreating the production resolver inside the bootstrap.
"""

from __future__ import annotations

from collections.abc import Iterable

from .ast_contract import AstNode
from .hir_contract import HirBinding, HirModule, HirNode, HirType, SourceSpan


_ARITHMETIC_SYMBOLS = {
    "add": "+",
    "subtract": "-",
    "multiply": "*",
    "divide": "/",
}
_COMPARISON_SYMBOLS = {
    "equal": "==",
    "not_equal": "!=",
    "greater_equal": ">=",
    "less_equal": "<=",
    "greater": ">",
    "less": "<",
}
_BOOL = HirType("bool")


class PrimitiveHirLoweringError(ValueError):
    """Raised when an AST node is outside the executable typed HIR slice."""


def _span(node: AstNode) -> SourceSpan:
    return SourceSpan(node.start, node.length)


def _validated_bindings(
    bindings: Iterable[tuple[str, HirType]],
) -> tuple[tuple[HirBinding, ...], dict[str, HirBinding]]:
    lowered: list[HirBinding] = []
    by_name: dict[str, HirBinding] = {}
    for binding_id, (name, type_) in enumerate(bindings):
        if not name:
            raise PrimitiveHirLoweringError("binding name must be non-empty")
        if name in by_name:
            raise PrimitiveHirLoweringError(f"duplicate resolved binding {name!r}")
        binding = HirBinding(binding_id, name, type_)
        lowered.append(binding)
        by_name[name] = binding
    return tuple(lowered), by_name


def _lower_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    bindings: Iterable[tuple[str, HirType]],
    module_name: str,
    allow_identifiers: bool,
    allow_comparisons: bool,
) -> HirModule:
    if not module_name:
        raise PrimitiveHirLoweringError("module name must be non-empty")
    if node.start < 0 or node.length < 0 or node.start + node.length > len(source):
        raise PrimitiveHirLoweringError("AST span is outside source text")

    hir_bindings, bindings_by_name = _validated_bindings(bindings)
    nodes: list[HirNode] = []

    def lower(current: AstNode) -> tuple[int, HirType]:
        if (
            current.start < 0
            or current.length < 0
            or current.start + current.length > len(source)
        ):
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
            return node_id, expected_type

        if current.kind == "identifier" and allow_identifiers:
            if current.children:
                raise PrimitiveHirLoweringError("identifier unexpectedly has children")
            name = source[current.start : current.start + current.length]
            binding = bindings_by_name.get(name)
            if binding is None:
                raise PrimitiveHirLoweringError(f"unresolved identifier {name!r}")
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "identifier",
                    binding.type,
                    span=_span(current),
                    binding_id=binding.binding_id,
                    ownership="value",
                )
            )
            return node_id, binding.type

        symbol = _ARITHMETIC_SYMBOLS.get(current.kind)
        if symbol is not None:
            if len(current.children) != 2:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} requires exactly two AST children"
                )
            left, left_type = lower(current.children[0])
            right, right_type = lower(current.children[1])
            if left_type != expected_type or right_type != expected_type:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} operands must both be {expected_type.name}"
                )
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
            return node_id, expected_type

        symbol = _COMPARISON_SYMBOLS.get(current.kind)
        if symbol is not None and allow_comparisons:
            if len(current.children) != 2:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} requires exactly two AST children"
                )
            left, left_type = lower(current.children[0])
            right, right_type = lower(current.children[1])
            if left_type != expected_type or right_type != expected_type:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} operands must both be {expected_type.name}"
                )
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "binary",
                    _BOOL,
                    children=(left, right),
                    span=_span(current),
                    symbol=symbol,
                    numeric_policy="exact",
                )
            )
            return node_id, _BOOL

        raise PrimitiveHirLoweringError(
            f"AST kind {current.kind!r} is outside executable HIR v1"
        )

    root, _ = lower(node)
    return HirModule(module_name, hir_bindings, tuple(nodes), (root,))


def lower_primitive_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    module_name: str = "expression",
) -> HirModule:
    """Lower exact numeric literals and primitive arithmetic to typed HIR."""

    return _lower_expression_hir(
        node,
        source,
        expected_type=expected_type,
        bindings=(),
        module_name=module_name,
        allow_identifiers=False,
        allow_comparisons=False,
    )


def lower_bound_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    bindings: Iterable[tuple[str, HirType]],
    module_name: str = "expression",
) -> HirModule:
    """Lower the binding-aware arithmetic/comparison bootstrap expression slice.

    ``bindings`` is an ordered semantic environment. Its order defines stable
    binding IDs, making name resolution explicit and deterministic on both sides
    of the bootstrap parity boundary. Identifiers and arithmetic operands must
    resolve to ``expected_type``; comparison results are ``bool``.
    """

    return _lower_expression_hir(
        node,
        source,
        expected_type=expected_type,
        bindings=bindings,
        module_name=module_name,
        allow_identifiers=True,
        allow_comparisons=True,
    )
