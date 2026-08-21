"""Destructor-aware C emission for ownership-validated bootstrap MIR.

This module consumes a validated ``bootstrap-mir-abi-v1`` module together with
its ``bootstrap-mir-ownership-v1`` proof.  Return-edge cleanup actions are
materialized as ordered destructor calls immediately before the corresponding C
return.  No destructor is inferred from a C type: every owned MIR type must have
an explicit, validated destructor binding.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature
from merit.bootstrap.mir_abi_to_c import (
    MirAbiToCError,
    _abi_instruction,
    _c_name,
    _signature_parameter_list,
    _validate_c_names,
)
from merit.bootstrap.mir_contract import MirFunction, MirType
from merit.bootstrap.mir_ownership import OwnershipPlan, analyze_ownership
from merit.bootstrap.mir_to_c import (
    _CHECKED_HELPERS,
    _checked_helpers,
    _function_table,
    _identifier,
    _local,
    _terminator,
    _type,
)

CLEANUP_C_SCHEMA = "bootstrap-cleanup-c-v1"


class MirCleanupToCError(MirAbiToCError):
    """Raised when ownership-safe MIR cannot be emitted with explicit cleanup."""


@dataclass(frozen=True, slots=True)
class DestructorBinding:
    """Explicit mapping from one MIR type to one stable C destructor symbol."""

    type: MirType
    symbol: str

    def __post_init__(self) -> None:
        if not self.symbol:
            raise MirCleanupToCError("destructor symbols must be non-empty")
        if _identifier(self.symbol) != self.symbol:
            raise MirCleanupToCError(
                f"destructor symbol {self.symbol!r} must already be a valid C identifier"
            )

    def to_data(self) -> dict[str, object]:
        return {"type": self.type.to_data(), "symbol": self.symbol}


@dataclass(frozen=True, slots=True)
class CleanupCPolicy:
    """Versioned destructor policy used to materialize ownership cleanup."""

    destructors: tuple[DestructorBinding, ...]
    schema: str = CLEANUP_C_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CLEANUP_C_SCHEMA:
            raise MirCleanupToCError(f"expected cleanup C schema {CLEANUP_C_SCHEMA!r}")
        type_keys = [binding.type for binding in self.destructors]
        symbols = [binding.symbol for binding in self.destructors]
        if len(type_keys) != len(set(type_keys)):
            raise MirCleanupToCError("duplicate destructor type binding")
        if len(symbols) != len(set(symbols)):
            raise MirCleanupToCError("duplicate destructor symbol")

    def destructor_map(self) -> dict[MirType, str]:
        return {binding.type: binding.symbol for binding in self.destructors}

    def to_data(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "destructors": [binding.to_data() for binding in self.destructors],
        }


def canonical_cleanup_policy_json(policy: CleanupCPolicy) -> str:
    return json.dumps(policy.to_data(), sort_keys=True, separators=(",", ":"))


def _plan_map(plan: OwnershipPlan) -> dict[str, object]:
    return {function.function: function for function in plan.functions}


def _validate_plan(abi: MirAbiModule, plan: OwnershipPlan) -> None:
    function_names = [function.name for function in abi.module.functions]
    plan_names = [function.function for function in plan.functions]
    if function_names != plan_names:
        raise MirCleanupToCError(
            "ownership plan functions must exactly match MIR module order"
        )


def _validate_destructors(
    abi: MirAbiModule,
    plan: OwnershipPlan,
    policy: CleanupCPolicy,
) -> dict[MirType, str]:
    destructors = policy.destructor_map()
    functions = {function.name: function for function in abi.module.functions}
    required: set[MirType] = set()
    for function_plan in plan.functions:
        function = functions[function_plan.function]
        locals_ = {local.local_id: local for local in function.locals}
        for action in function_plan.cleanup_actions:
            local = locals_.get(action.local_id)
            if local is None:
                raise MirCleanupToCError(
                    f"cleanup action references unknown local {action.local_id}"
                )
            if local.ownership != "owned":
                raise MirCleanupToCError(
                    f"cleanup action references non-owned local {action.local_id}"
                )
            required.add(local.type)
    missing = sorted(type_.name for type_ in required if type_ not in destructors)
    if missing:
        raise MirCleanupToCError(f"missing destructor bindings for owned types: {missing}")

    occupied = {_c_name(signature) for signature in abi.signatures}
    for symbol in destructors.values():
        if symbol in occupied:
            raise MirCleanupToCError(
                f"destructor symbol {symbol!r} collides with an emitted function"
            )
    return destructors


def _destructor_prototypes(policy: CleanupCPolicy) -> list[str]:
    return [
        f"void {binding.symbol}({_type(binding.type)} value);"
        for binding in policy.destructors
    ]


def _emit_cleanup_function(
    function: MirFunction,
    signature: MirFunctionSignature,
    functions: dict[str, MirFunction],
    signatures: dict[str, MirFunctionSignature],
    function_plan: object,
    destructors: Mapping[MirType, str],
) -> str:
    return_type = _type(function.return_type)
    lines = [
        f"{return_type} {_c_name(signature)}"
        f"({_signature_parameter_list(signature)}) {{"
    ]
    parameter_locals = {parameter.local_id for parameter in signature.parameters}
    for local in function.locals:
        local_type = _type(local.type)
        if local_type == "void":
            raise MirCleanupToCError("MIR locals cannot have unit type in cleanup emission")
        if local.local_id in parameter_locals:
            continue
        lines.append(f"    {local_type} {_local(local.local_id)} = 0;")
    for index, parameter in enumerate(signature.parameters):
        local_name = _local(parameter.local_id)
        lines.append(f"    {_type(parameter.type)} {local_name} = p{index};")
        lines.append(f"    (void){local_name};")
    lines.append(f"    goto b{function.entry_block};")

    cleanup_by_block: dict[int, list[object]] = {}
    for action in function_plan.cleanup_actions:
        cleanup_by_block.setdefault(action.block_id, []).append(action)
    locals_ = {local.local_id: local for local in function.locals}

    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _abi_instruction(instruction, functions, signatures):
                lines.append(f"    {statement}")
        if block.terminator.kind == "return":
            actions = sorted(cleanup_by_block.get(block.block_id, ()), key=lambda item: item.order)
            for action in actions:
                local = locals_[action.local_id]
                symbol = destructors[local.type]
                lines.append(f"    {symbol}({_local(local.local_id)});")
        for statement in _terminator(block.terminator, return_type):
            lines.append(f"    {statement}")
    lines.append("}")
    return "\n".join(lines)


def emit_c_abi_module_with_cleanup(
    abi: MirAbiModule,
    policy: CleanupCPolicy,
    *,
    ownership_plan: OwnershipPlan | None = None,
) -> str:
    """Emit deterministic C with explicit exact-once return-edge cleanup.

    The ownership proof is recomputed by default.  A supplied plan is accepted
    only when its function set and order exactly match the MIR ABI module.
    """

    _validate_c_names(abi)
    plan = ownership_plan or analyze_ownership(abi)
    _validate_plan(abi, plan)
    destructors = _validate_destructors(abi, plan, policy)

    module = abi.module
    functions = _function_table(module)
    signatures = abi.signature_map()
    plans = _plan_map(plan)
    instructions = [
        instruction
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    needs_contract = any(instruction.kind == "contract_check" for instruction in instructions)
    needs_capability = any(instruction.kind == "capability_check" for instruction in instructions)
    needs_print = any(instruction.kind == "print" for instruction in instructions)
    checked_operators = {
        instruction.symbol
        for instruction in instructions
        if instruction.kind == "binary"
        and instruction.numeric_policy == "checked"
        and instruction.symbol in _CHECKED_HELPERS
    }

    prelude = [
        "/* generated from bootstrap-cleanup-c-v1; deterministic, do not edit */",
        "#include <stdbool.h>",
        "#include <stdint.h>",
        *(["#include <stdio.h>"] if needs_print else []),
        "#include <stdlib.h>",
        "",
    ]
    runtime = _checked_helpers(checked_operators)
    if needs_contract:
        runtime.append(
            "static void merit_contract_failure(const char *kind) { (void)kind; abort(); }"
        )
    if needs_capability:
        runtime.append(
            "static void merit_capability_check(const char *capability) { (void)capability; }"
        )
    if runtime:
        prelude.extend([*runtime, ""])
    destructor_prototypes = _destructor_prototypes(policy)
    if destructor_prototypes:
        prelude.extend([*destructor_prototypes, ""])
    prototypes = [
        f"{_type(function.return_type)} {_c_name(signatures[function.name])}"
        f"({_signature_parameter_list(signatures[function.name])});"
        for function in module.functions
    ]
    if prototypes:
        prelude.extend([*prototypes, ""])

    emitted = "\n\n".join(
        _emit_cleanup_function(
            function,
            signatures[function.name],
            functions,
            signatures,
            plans[function.name],
            destructors,
        )
        for function in module.functions
    )
    return "\n".join([*prelude, emitted, ""])
