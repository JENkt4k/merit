"""Deterministic C emission from ``bootstrap-mir-v1``.

The emitter consumes already ordered MIR. It never reconstructs Merit
expression trees and therefore cannot reintroduce unspecified C evaluation
order. The first supported slice is intentionally strict: scalar i64/bool/unit
functions, explicit basic blocks, arithmetic, copies, conversions, contracts,
and branch/jump/switch/return terminators.
"""

from __future__ import annotations

import json
import re

from merit.bootstrap.mir_contract import MirFunction, MirInstruction, MirModule, MirTerminator, MirType


class MirToCError(ValueError):
    """Raised when MIR is outside the supported deterministic C subset."""


_C_TYPES = {"i64": "int64_t", "bool": "bool", "unit": "void"}
_BINARY = {
    "+": "+", "-": "-", "*": "*", "/": "/", "%": "%",
    "==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
    "&&": "&&", "||": "||", "&": "&", "|": "|", "^": "^",
}


def _identifier(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "merit_" + cleaned
    return cleaned


def _type(type_: MirType) -> str:
    if type_.arguments:
        raise MirToCError(f"generic MIR type is not supported by the core C emitter: {type_.name}")
    try:
        return _C_TYPES[type_.name]
    except KeyError as error:
        raise MirToCError(f"unsupported MIR type for C emission: {type_.name}") from error


def _literal(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return f"INT64_C({value})"
    raise MirToCError(f"unsupported MIR constant for C emission: {value!r}")


def _local(local_id: int) -> str:
    return f"m{local_id}"


def _instruction(instruction: MirInstruction) -> list[str]:
    result = _local(instruction.result) if instruction.result is not None else None
    operands = [_local(value) for value in instruction.operands]
    kind = instruction.kind
    if kind == "const":
        if result is None:
            raise MirToCError("const instruction requires a result")
        return [f"{result} = {_literal(instruction.value)};"]
    if kind in {"copy", "move", "borrow"}:
        if result is None or len(operands) != 1:
            raise MirToCError(f"{kind} instruction requires one operand and a result")
        return [f"{result} = {operands[0]};"]
    if kind == "binary":
        if result is None or len(operands) != 2 or instruction.symbol not in _BINARY:
            raise MirToCError("binary instruction requires a supported operator, two operands, and a result")
        if instruction.numeric_policy not in {"exact", "checked", "floating"}:
            raise MirToCError(f"numeric policy not supported by core C emission: {instruction.numeric_policy}")
        expression = f"{operands[0]} {_BINARY[instruction.symbol]} {operands[1]}"
        return [f"{result} = {expression};"]
    if kind == "convert":
        if result is None or len(operands) != 1:
            raise MirToCError("convert instruction requires one operand and a result")
        if instruction.conversion_policy not in {"exact", "checked"}:
            raise MirToCError(f"conversion policy not supported by core C emission: {instruction.conversion_policy}")
        return [f"{result} = {operands[0]};"]
    if kind == "contract_check":
        if len(operands) != 1:
            raise MirToCError("contract check requires one condition")
        return [f"if (!{operands[0]}) merit_contract_failure({json.dumps(instruction.contract_kind)});"]
    if kind == "capability_check":
        return [f"merit_capability_check({json.dumps(capability)});" for capability in instruction.capabilities]
    if kind in {"drop", "deallocate", "nop"}:
        return ["/* explicit no-op in scalar bootstrap C subset */"]
    raise MirToCError(f"unsupported MIR instruction for C emission: {kind}")


def _terminator(terminator: MirTerminator, return_type: str) -> list[str]:
    if terminator.kind == "return":
        if terminator.operands:
            return [f"return {_local(terminator.operands[0])};"]
        return ["return;" if return_type == "void" else "return 0;"]
    if terminator.kind == "jump":
        return [f"goto b{terminator.targets[0]};"]
    if terminator.kind == "branch":
        return [f"if ({_local(terminator.operands[0])}) goto b{terminator.targets[0]};", f"goto b{terminator.targets[1]};"]
    if terminator.kind == "switch":
        lines = [f"switch ({_local(terminator.operands[0])}) {{"]
        for case, target in zip(terminator.cases, terminator.targets[:-1]):
            lines.append(f"case {case}: goto b{target};")
        lines.append(f"default: goto b{terminator.targets[-1]};")
        lines.append("}")
        return lines
    if terminator.kind == "unreachable":
        return ["abort();"]
    raise MirToCError(f"unsupported MIR terminator: {terminator.kind}")


def emit_c_function(function: MirFunction) -> str:
    return_type = _type(function.return_type)
    name = _identifier(function.name)
    lines = [f"{return_type} {name}(void) {{"]
    for local in function.locals:
        local_type = _type(local.type)
        if local_type == "void":
            raise MirToCError("MIR locals cannot have unit type in core C emission")
        lines.append(f"    {local_type} {_local(local.local_id)} = 0;")
    lines.append(f"    goto b{function.entry_block};")
    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _instruction(instruction):
                lines.append(f"    {statement}")
        for statement in _terminator(block.terminator, return_type):
            lines.append(f"    {statement}")
    lines.append("}")
    return "\n".join(lines)


def emit_c_module(module: MirModule) -> str:
    functions = "\n\n".join(emit_c_function(function) for function in module.functions)
    return "\n".join([
        "/* generated from bootstrap-mir-v1; deterministic, do not edit */",
        "#include <stdbool.h>",
        "#include <stdint.h>",
        "#include <stdlib.h>",
        "",
        "static void merit_contract_failure(const char *kind) { (void)kind; abort(); }",
        "static void merit_capability_check(const char *capability) { (void)capability; }",
        "",
        functions,
        "",
    ])
