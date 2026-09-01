"""C emission for MIR whose cleanup is already explicit.

Unlike ``mir_cleanup_to_c``, this backend does not consult an ownership plan at
emission time.  It first materializes cleanup into MIR and then emits every
symbol-bearing ``drop``/``deallocate`` as an ordinary ordered C call.
"""

from __future__ import annotations

from merit.bootstrap.mir_abi import MirAbiModule, MirFunctionSignature
from merit.bootstrap.mir_abi_to_c import (
    MirAbiToCError,
    _abi_instruction,
    _c_name,
    _signature_parameter_list,
    _validate_c_names,
)
from merit.bootstrap.mir_cleanup_materialize import materialize_cleanup_mir
from merit.bootstrap.mir_cleanup_to_c import CleanupCPolicy
from merit.bootstrap.mir_contract import MirFunction, MirInstruction, MirType
from merit.bootstrap.mir_to_c import (
    _CHECKED_HELPERS,
    _INTEGER_TYPES,
    _checked_helpers,
    _function_table,
    _identifier,
    _local,
    _terminator,
    _type,
)


class MirMaterializedToCError(MirAbiToCError):
    """Raised when explicit cleanup MIR is outside the supported C subset."""


def _instruction(
    instruction: MirInstruction,
    functions: dict[str, MirFunction],
    signatures: dict[str, MirFunctionSignature],
    local_types: dict[int, MirType],
    local_ownership: dict[int, str],
) -> list[str]:
    if instruction.kind in {"drop", "deallocate"}:
        if len(instruction.operands) != 1 or not instruction.symbol:
            raise MirMaterializedToCError(
                f"materialized {instruction.kind} requires one operand and destructor symbol"
            )
        symbol = _identifier(instruction.symbol)
        if symbol != instruction.symbol:
            raise MirMaterializedToCError("destructor symbols must be valid C identifiers")
        return [f"{symbol}({_local(instruction.operands[0])});"]
    return _abi_instruction(
        instruction, functions, signatures, local_types, local_ownership
    )


def _emit_function(function, signature, functions, signatures) -> str:
    return_type = _type(function.return_type)
    local_types = {local.local_id: local.type for local in function.locals}
    local_ownership = {local.local_id: local.ownership for local in function.locals}
    lines = [f"{return_type} {_c_name(signature)}({_signature_parameter_list(signature)}) {{"]
    parameter_locals = {parameter.local_id for parameter in signature.parameters}
    for local in function.locals:
        local_type = _type(local.type)
        if local_type == "void":
            raise MirMaterializedToCError("MIR locals cannot have unit type")
        if local.local_id not in parameter_locals:
            lines.append(f"    {local_type} {_local(local.local_id)} = 0;")
    for index, parameter in enumerate(signature.parameters):
        name = _local(parameter.local_id)
        lines.append(f"    {_type(parameter.type)} {name} = p{index};")
        lines.append(f"    (void){name};")
    lines.append(f"    goto b{function.entry_block};")
    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _instruction(
                instruction,
                functions,
                signatures,
                local_types,
                local_ownership,
            ):
                lines.append(f"    {statement}")
        for statement in _terminator(block.terminator, return_type):
            lines.append(f"    {statement}")
    lines.append("}")
    return "\n".join(lines)


def emit_c_materialized_cleanup(abi: MirAbiModule, policy: CleanupCPolicy) -> str:
    """Materialize ownership cleanup into MIR and emit deterministic C."""

    materialized = materialize_cleanup_mir(abi, policy)
    _validate_c_names(materialized)
    functions = _function_table(materialized.module)
    signatures = materialized.signature_map()
    instructions = [
        instruction
        for function in materialized.module.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    needs_print = any(instruction.kind == "print" for instruction in instructions)
    checked_operators: set[tuple[str, str]] = set()
    for function in materialized.module.functions:
        local_types = {local.local_id: local.type for local in function.locals}
        for block in function.blocks:
            for instruction in block.instructions:
                if (
                    instruction.kind == "binary"
                    and instruction.numeric_policy == "checked"
                    and instruction.symbol in _CHECKED_HELPERS
                    and instruction.result is not None
                    and local_types[instruction.result].name in _INTEGER_TYPES
                ):
                    checked_operators.add(
                        (local_types[instruction.result].name, instruction.symbol)
                    )
    prelude = [
        "/* generated from bootstrap-mir-cleanup-v1; deterministic, do not edit */",
        "#include <stdbool.h>",
        "#include <stdint.h>",
        *(["#include <stdio.h>"] if needs_print or checked_operators else []),
        "#include <stdlib.h>",
        "",
    ]
    runtime = _checked_helpers(checked_operators)
    if any(instruction.kind == "contract_check" for instruction in instructions):
        runtime.append("static void merit_contract_failure(const char *kind) { (void)kind; abort(); }")
    if any(instruction.kind == "capability_check" for instruction in instructions):
        runtime.append("static void merit_capability_check(const char *capability) { (void)capability; }")
    if runtime:
        prelude.extend([*runtime, ""])
    destructor_prototypes = [
        f"void {binding.symbol}({_type(binding.type)} value);"
        for binding in policy.destructors
    ]
    if destructor_prototypes:
        prelude.extend([*destructor_prototypes, ""])
    prototypes = [
        f"{_type(function.return_type)} {_c_name(signatures[function.name])}"
        f"({_signature_parameter_list(signatures[function.name])});"
        for function in materialized.module.functions
    ]
    if prototypes:
        prelude.extend([*prototypes, ""])
    bodies = "\n\n".join(
        _emit_function(function, signatures[function.name], functions, signatures)
        for function in materialized.module.functions
    )
    return "\n".join([*prelude, bodies, ""])
