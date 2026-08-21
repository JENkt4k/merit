"""Deterministic C emission for ``bootstrap-mir-abi-v1``.

This emitter extends the core MIR backend with explicit scalar parameters while
reusing the core backend's checked arithmetic, control-flow, and runtime helper
implementation. Argument order is exactly the ABI signature order and each
parameter is bound to its declared MIR local at function entry.
"""

from __future__ import annotations

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature
from merit.bootstrap.mir_contract import MirFunction, MirInstruction
from merit.bootstrap.mir_to_c import (
    MirToCError,
    _CHECKED_HELPERS,
    _checked_helpers,
    _function_table,
    _identifier,
    _instruction,
    _local,
    _terminator,
    _type,
)


class MirAbiToCError(MirToCError):
    """Raised when a valid ABI is outside the supported scalar C subset."""


def _c_name(signature: MirFunctionSignature) -> str:
    return _identifier(signature.exported_name or signature.function)


def _signature_parameter_list(signature: MirFunctionSignature) -> str:
    if not signature.parameters:
        return "void"
    return ", ".join(
        f"{_type(parameter.type)} p{index}"
        for index, parameter in enumerate(signature.parameters)
    )


def _validate_c_names(abi: MirAbiModule) -> None:
    seen: dict[str, str] = {}
    for signature in abi.signatures:
        c_name = _c_name(signature)
        previous = seen.get(c_name)
        if previous is not None and previous != signature.function:
            raise MirAbiToCError(
                f"ABI functions {previous!r} and {signature.function!r} collide as C identifier {c_name!r}"
            )
        seen[c_name] = signature.function


def _abi_instruction(
    instruction: MirInstruction,
    functions: dict[str, MirFunction],
    signatures: dict[str, MirFunctionSignature],
) -> list[str]:
    if instruction.kind != "call":
        return _instruction(instruction, functions)
    if not instruction.symbol:
        raise MirAbiToCError("call instruction requires a resolved symbol")
    callee = functions.get(instruction.symbol)
    signature = signatures.get(instruction.symbol)
    if callee is None or signature is None:
        raise MirAbiToCError(f"call references unknown ABI function: {instruction.symbol}")
    if len(instruction.operands) != len(signature.parameters):
        raise MirAbiToCError(
            f"call to {instruction.symbol} expects {len(signature.parameters)} arguments, "
            f"got {len(instruction.operands)}"
        )
    arguments = ", ".join(_local(local_id) for local_id in instruction.operands)
    call = f"{_c_name(signature)}({arguments})"
    result = _local(instruction.result) if instruction.result is not None else None
    callee_type = _type(callee.return_type)
    if callee_type == "void":
        if result is not None:
            raise MirAbiToCError("unit-returning ABI calls cannot produce a result local")
        return [f"{call};"]
    if result is None:
        raise MirAbiToCError("value-returning ABI calls require a result local")
    return [f"{result} = {call};"]


def _prototype(function: MirFunction, signature: MirFunctionSignature) -> str:
    return (
        f"{_type(function.return_type)} {_c_name(signature)}"
        f"({_signature_parameter_list(signature)});"
    )


def emit_c_abi_function(
    function: MirFunction,
    signature: MirFunctionSignature,
    functions: dict[str, MirFunction],
    signatures: dict[str, MirFunctionSignature],
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
            raise MirAbiToCError("MIR locals cannot have unit type in scalar ABI emission")
        if local.local_id in parameter_locals:
            continue
        lines.append(f"    {local_type} {_local(local.local_id)} = 0;")
    for index, parameter in enumerate(signature.parameters):
        local_name = _local(parameter.local_id)
        lines.append(f"    {_type(parameter.type)} {local_name} = p{index};")
        # Keep deliberately unused parameters warning-clean under -Werror while
        # retaining an explicit MIR-local binding for later ownership passes.
        lines.append(f"    (void){local_name};")
    lines.append(f"    goto b{function.entry_block};")
    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _abi_instruction(instruction, functions, signatures):
                lines.append(f"    {statement}")
        for statement in _terminator(block.terminator, return_type):
            lines.append(f"    {statement}")
    lines.append("}")
    return "\n".join(lines)


def emit_c_abi_module(abi: MirAbiModule) -> str:
    _validate_c_names(abi)
    module = abi.module
    functions = _function_table(module)
    signatures = abi.signature_map()
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
        "/* generated from bootstrap-mir-abi-v1; deterministic, do not edit */",
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
    prototypes = [
        _prototype(function, signatures[function.name])
        for function in module.functions
    ]
    if prototypes:
        prelude.extend([*prototypes, ""])
    emitted = "\n\n".join(
        emit_c_abi_function(function, signatures[function.name], functions, signatures)
        for function in module.functions
    )
    return "\n".join([*prelude, emitted, ""])
