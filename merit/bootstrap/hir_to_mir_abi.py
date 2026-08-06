"""Derive ``bootstrap-mir-abi-v1`` directly from checked HIR.

Function parameter nodes are semantic declarations, not executable statements.
This bridge validates their binding, type, ownership, mutability, and source
order; removes them from executable HIR before ordinary HIR-to-MIR lowering;
and derives the corresponding MIR ABI signatures deterministically.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType
from merit.bootstrap.hir_to_mir import HirToMirError, lower_hir_to_mir
from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature, MirParameter
from merit.bootstrap.mir_contract import MirType


class HirToMirAbiError(HirToMirError):
    """Raised when checked HIR cannot define the scalar bootstrap ABI."""


def _mir_type(type_: HirType) -> MirType:
    return MirType(type_.name, tuple(_mir_type(argument) for argument in type_.arguments))


def _function_roots(module: HirModule) -> tuple[HirNode, ...]:
    by_id = {node.node_id: node for node in module.nodes}
    roots: list[HirNode] = []
    names: set[str] = set()
    for root_id in module.roots:
        function = by_id[root_id]
        if function.kind != "function" or not function.symbol:
            raise HirToMirAbiError(f"root node {root_id} is not a resolved function")
        if function.symbol in names:
            raise HirToMirAbiError(f"duplicate HIR function symbol: {function.symbol}")
        names.add(function.symbol)
        roots.append(function)
    return tuple(roots)


def _leading_parameters(function: HirNode, by_id: Mapping[int, HirNode]) -> tuple[HirNode, ...]:
    parameters: list[HirNode] = []
    body_started = False
    for child_id in function.children:
        child = by_id[child_id]
        if child.kind == "parameter":
            if body_started:
                raise HirToMirAbiError(
                    f"function {function.symbol} has a parameter after executable body nodes"
                )
            parameters.append(child)
        else:
            body_started = True
    return tuple(parameters)


def _validate_parameter(
    function: HirNode,
    parameter: HirNode,
    bindings: Mapping[int, HirBinding],
) -> HirBinding:
    if parameter.binding_id is None:
        raise HirToMirAbiError(
            f"parameter node {parameter.node_id} in {function.symbol} has no binding"
        )
    binding = bindings.get(parameter.binding_id)
    if binding is None:
        raise HirToMirAbiError(
            f"parameter node {parameter.node_id} references unknown binding {parameter.binding_id}"
        )
    if parameter.children:
        raise HirToMirAbiError(f"parameter node {parameter.node_id} cannot have children")
    if parameter.type != binding.type:
        raise HirToMirAbiError(
            f"parameter {binding.name} type does not match binding {binding.binding_id}"
        )
    ownership = parameter.ownership if parameter.ownership != "none" else binding.ownership
    if ownership != binding.ownership:
        raise HirToMirAbiError(
            f"parameter {binding.name} ownership does not match binding {binding.binding_id}"
        )
    if binding.ownership not in {"value", "owned", "borrowed", "mutable_borrow"}:
        raise HirToMirAbiError(
            f"parameter {binding.name} has unsupported scalar ABI ownership {binding.ownership!r}"
        )
    return binding


def _validate_calls(
    module: HirModule,
    parameters_by_function: Mapping[str, tuple[HirNode, ...]],
) -> None:
    by_id = {node.node_id: node for node in module.nodes}
    bindings = {binding.binding_id: binding for binding in module.bindings}
    for node in module.nodes:
        if node.kind != "call":
            continue
        if not node.symbol or node.symbol not in parameters_by_function:
            raise HirToMirAbiError(
                f"call node {node.node_id} references unknown HIR function {node.symbol!r}"
            )
        expected = parameters_by_function[node.symbol]
        if len(node.children) != len(expected):
            raise HirToMirAbiError(
                f"call to {node.symbol} expects {len(expected)} arguments, got {len(node.children)}"
            )
        for index, (argument_id, parameter) in enumerate(zip(node.children, expected)):
            argument = by_id[argument_id]
            binding = bindings[parameter.binding_id]  # validated before call checking
            if argument.type != binding.type:
                raise HirToMirAbiError(
                    f"call to {node.symbol} argument {index} type {argument.type.name!r} "
                    f"does not match parameter {binding.name} type {binding.type.name!r}"
                )
            if binding.ownership == "owned" and argument.ownership not in {"owned", "moved"}:
                raise HirToMirAbiError(
                    f"call to {node.symbol} argument {index} must transfer an owned value"
                )
            if binding.ownership == "borrowed" and argument.ownership not in {"borrowed", "none"}:
                raise HirToMirAbiError(
                    f"call to {node.symbol} argument {index} must be an immutable borrow"
                )
            if binding.ownership == "mutable_borrow" and argument.ownership != "mutable_borrow":
                raise HirToMirAbiError(
                    f"call to {node.symbol} argument {index} must be a mutable borrow"
                )


def lower_hir_to_mir_abi(
    module: HirModule,
    *,
    exported_names: Mapping[str, str] | None = None,
) -> MirAbiModule:
    """Lower checked HIR and derive ordered scalar MIR ABI signatures.

    ``exported_names`` is an explicit policy input rather than parser metadata;
    keys must name functions in the module and values become stable C symbols.
    """

    exported_names = dict(exported_names or {})
    by_id = {node.node_id: node for node in module.nodes}
    bindings = {binding.binding_id: binding for binding in module.bindings}
    functions = _function_roots(module)

    parameters_by_function: dict[str, tuple[HirNode, ...]] = {}
    parameter_bindings: dict[str, tuple[HirBinding, ...]] = {}
    for function in functions:
        parameters = _leading_parameters(function, by_id)
        validated = tuple(_validate_parameter(function, parameter, bindings) for parameter in parameters)
        if len({binding.binding_id for binding in validated}) != len(validated):
            raise HirToMirAbiError(f"function {function.symbol} repeats a parameter binding")
        if len({binding.name for binding in validated}) != len(validated):
            raise HirToMirAbiError(f"function {function.symbol} repeats a parameter name")
        parameters_by_function[function.symbol] = parameters
        parameter_bindings[function.symbol] = validated

    unknown_exports = sorted(set(exported_names) - set(parameters_by_function))
    if unknown_exports:
        raise HirToMirAbiError(f"export policy references unknown functions: {unknown_exports}")

    _validate_calls(module, parameters_by_function)

    stripped_functions = {
        function.node_id: replace(
            function,
            children=tuple(
                child_id for child_id in function.children if by_id[child_id].kind != "parameter"
            ),
        )
        for function in functions
    }
    stripped_nodes = tuple(stripped_functions.get(node.node_id, node) for node in module.nodes)
    executable_hir = HirModule(
        module.name,
        module.bindings,
        stripped_nodes,
        module.roots,
        module.schema,
    )
    mir = lower_hir_to_mir(executable_hir)

    # The core lowerer assigns binding-backed locals first in ascending binding-ID order.
    binding_local = {
        binding.binding_id: index
        for index, binding in enumerate(sorted(module.bindings, key=lambda item: item.binding_id))
    }
    signatures = tuple(
        MirFunctionSignature(
            function.symbol,
            tuple(
                MirParameter(
                    binding.name,
                    binding_local[binding.binding_id],
                    _mir_type(binding.type),
                    binding.ownership,
                    binding.mutable,
                )
                for binding in parameter_bindings[function.symbol]
            ),
            exported_names.get(function.symbol),
        )
        for function in functions
    )
    return MirAbiModule(mir, signatures)
