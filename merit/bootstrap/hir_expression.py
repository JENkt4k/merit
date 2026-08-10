"""Typed-expression lowering into ``bootstrap-hir-v1``.

The bootstrap HIR boundary is deliberately explicit: callers provide resolved
binding types, function signatures, field signatures, and numeric destination
types instead of asking this layer to perform inference. That keeps
differential comparison focused on semantic lowering rather than recreating
the production resolver inside the bootstrap.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class HirFunctionSignature:
    """Resolved callable input supplied to the bootstrap HIR boundary."""

    symbol: str
    parameters: tuple[HirType, ...]
    result: HirType

    def __post_init__(self) -> None:
        if not self.symbol:
            raise PrimitiveHirLoweringError("function symbol must be non-empty")


@dataclass(frozen=True, slots=True)
class HirFieldSignature:
    """Resolved aggregate-field input supplied to the bootstrap HIR boundary."""

    receiver: HirType
    symbol: str
    result: HirType

    def __post_init__(self) -> None:
        if not self.symbol:
            raise PrimitiveHirLoweringError("field symbol must be non-empty")


def _span(node: AstNode) -> SourceSpan:
    return SourceSpan(node.start, node.length)


def _source_text(node: AstNode, source: str) -> str:
    return source[node.start : node.start + node.length]


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


def _validated_functions(
    functions: Iterable[HirFunctionSignature],
) -> dict[str, HirFunctionSignature]:
    by_symbol: dict[str, HirFunctionSignature] = {}
    for function in functions:
        if function.symbol in by_symbol:
            raise PrimitiveHirLoweringError(
                f"duplicate resolved function {function.symbol!r}"
            )
        by_symbol[function.symbol] = function
    return by_symbol


def _validated_fields(
    fields: Iterable[HirFieldSignature],
) -> dict[tuple[HirType, str], HirFieldSignature]:
    by_key: dict[tuple[HirType, str], HirFieldSignature] = {}
    for field in fields:
        key = (field.receiver, field.symbol)
        if key in by_key:
            raise PrimitiveHirLoweringError(
                f"duplicate resolved field {field.receiver.name}.{field.symbol}"
            )
        by_key[key] = field
    return by_key


def _argument_nodes(node: AstNode) -> tuple[AstNode, ...]:
    """Flatten parser sequence nodes into stable source argument order."""

    if node.kind != "sequence":
        return (node,)
    if len(node.children) != 2:
        raise PrimitiveHirLoweringError("argument sequence requires exactly two children")
    return _argument_nodes(node.children[0]) + _argument_nodes(node.children[1])


def _lower_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    bindings: Iterable[tuple[str, HirType]],
    functions: Iterable[HirFunctionSignature],
    fields: Iterable[HirFieldSignature],
    module_name: str,
    allow_identifiers: bool,
    allow_comparisons: bool,
    allow_calls: bool,
    allow_fields: bool,
) -> HirModule:
    if not module_name:
        raise PrimitiveHirLoweringError("module name must be non-empty")
    if node.start < 0 or node.length < 0 or node.start + node.length > len(source):
        raise PrimitiveHirLoweringError("AST span is outside source text")

    hir_bindings, bindings_by_name = _validated_bindings(bindings)
    functions_by_symbol = _validated_functions(functions)
    fields_by_key = _validated_fields(fields)
    nodes: list[HirNode] = []

    def lower(current: AstNode, contextual_type: HirType | None) -> tuple[int, HirType]:
        if (
            current.start < 0
            or current.length < 0
            or current.start + current.length > len(source)
        ):
            raise PrimitiveHirLoweringError("AST span is outside source text")

        if current.kind == "exact_numeric":
            if current.children:
                raise PrimitiveHirLoweringError("numeric literal unexpectedly has children")
            if contextual_type is None:
                raise PrimitiveHirLoweringError("numeric literal requires an explicit type")
            value = _source_text(current, source)
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "literal",
                    contextual_type,
                    span=_span(current),
                    value=value,
                    numeric_policy="exact",
                )
            )
            return node_id, contextual_type

        if current.kind == "identifier" and allow_identifiers:
            if current.children:
                raise PrimitiveHirLoweringError("identifier unexpectedly has children")
            name = _source_text(current, source)
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

        if current.kind == "call" and allow_calls:
            if len(current.children) not in {1, 2}:
                raise PrimitiveHirLoweringError("call requires callee and optional arguments")
            callee = current.children[0]
            if callee.kind != "identifier" or callee.children:
                raise PrimitiveHirLoweringError(
                    "executable HIR v1 calls require a resolved identifier callee"
                )
            symbol = _source_text(callee, source)
            signature = functions_by_symbol.get(symbol)
            if signature is None:
                raise PrimitiveHirLoweringError(f"unresolved function {symbol!r}")
            arguments = () if len(current.children) == 1 else _argument_nodes(current.children[1])
            if len(arguments) != len(signature.parameters):
                raise PrimitiveHirLoweringError(
                    f"function {symbol!r} expects {len(signature.parameters)} arguments, "
                    f"got {len(arguments)}"
                )
            child_ids: list[int] = []
            for argument, parameter_type in zip(arguments, signature.parameters, strict=True):
                child_id, argument_type = lower(argument, parameter_type)
                if argument_type != parameter_type:
                    raise PrimitiveHirLoweringError(
                        f"argument to {symbol!r} must be {parameter_type.name}, "
                        f"got {argument_type.name}"
                    )
                child_ids.append(child_id)
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "call",
                    signature.result,
                    children=tuple(child_ids),
                    span=_span(current),
                    symbol=symbol,
                    ownership="value",
                )
            )
            return node_id, signature.result

        if current.kind == "field" and allow_fields:
            if len(current.children) != 2:
                raise PrimitiveHirLoweringError("field access requires receiver and field name")
            receiver_ast, field_ast = current.children
            if field_ast.kind != "identifier" or field_ast.children:
                raise PrimitiveHirLoweringError("field name must be an identifier")
            receiver_id, receiver_type = lower(receiver_ast, None)
            symbol = _source_text(field_ast, source)
            signature = fields_by_key.get((receiver_type, symbol))
            if signature is None:
                raise PrimitiveHirLoweringError(
                    f"unresolved field {receiver_type.name}.{symbol}"
                )
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "field",
                    signature.result,
                    children=(receiver_id,),
                    span=_span(current),
                    symbol=symbol,
                    ownership="value",
                )
            )
            return node_id, signature.result

        symbol = _ARITHMETIC_SYMBOLS.get(current.kind)
        if symbol is not None:
            if len(current.children) != 2:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} requires exactly two AST children"
                )
            operation_type = expected_type if contextual_type is None else contextual_type
            left, left_type = lower(current.children[0], operation_type)
            right, right_type = lower(current.children[1], operation_type)
            if left_type != operation_type or right_type != operation_type:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} operands must both be {operation_type.name}"
                )
            node_id = len(nodes)
            nodes.append(
                HirNode(
                    node_id,
                    "binary",
                    operation_type,
                    children=(left, right),
                    span=_span(current),
                    symbol=symbol,
                    numeric_policy="checked",
                )
            )
            return node_id, operation_type

        symbol = _COMPARISON_SYMBOLS.get(current.kind)
        if symbol is not None and allow_comparisons:
            if len(current.children) != 2:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} requires exactly two AST children"
                )
            operation_type = expected_type if contextual_type is None else contextual_type
            left, left_type = lower(current.children[0], operation_type)
            right, right_type = lower(current.children[1], operation_type)
            if left_type != operation_type or right_type != operation_type:
                raise PrimitiveHirLoweringError(
                    f"{current.kind} operands must both be {operation_type.name}"
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

    root, _ = lower(node, expected_type)
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
        functions=(),
        fields=(),
        module_name=module_name,
        allow_identifiers=False,
        allow_comparisons=False,
        allow_calls=False,
        allow_fields=False,
    )


def lower_bound_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    bindings: Iterable[tuple[str, HirType]],
    module_name: str = "expression",
) -> HirModule:
    """Lower the binding-aware arithmetic/comparison bootstrap expression slice."""

    return _lower_expression_hir(
        node,
        source,
        expected_type=expected_type,
        bindings=bindings,
        functions=(),
        fields=(),
        module_name=module_name,
        allow_identifiers=True,
        allow_comparisons=True,
        allow_calls=False,
        allow_fields=False,
    )


def lower_resolved_expression_hir(
    node: AstNode,
    source: str,
    *,
    expected_type: HirType,
    bindings: Iterable[tuple[str, HirType]] = (),
    functions: Iterable[HirFunctionSignature] = (),
    fields: Iterable[HirFieldSignature] = (),
    module_name: str = "expression",
) -> HirModule:
    """Lower the resolved call/field expression slice into canonical HIR.

    All semantic inputs are explicit. ``bindings`` defines variable identities,
    ``functions`` defines callable parameter/result types, and ``fields`` defines
    field result types keyed by receiver type and field symbol. No lookup or
    inference is performed outside those supplied environments.
    """

    return _lower_expression_hir(
        node,
        source,
        expected_type=expected_type,
        bindings=bindings,
        functions=functions,
        fields=fields,
        module_name=module_name,
        allow_identifiers=True,
        allow_comparisons=True,
        allow_calls=True,
        allow_fields=True,
    )
