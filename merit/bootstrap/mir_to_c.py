"""Deterministic C emission from ``bootstrap-mir-v1``.

The emitter consumes already ordered MIR. It never reconstructs Merit
expression trees and therefore cannot reintroduce unspecified C evaluation
order. The supported bootstrap slice is deliberately strict: scalar
``i64``/``bool``/``unit`` functions, explicit basic blocks, ordered scalar
operations, checked integer arithmetic, validated no-argument calls, contracts,
capabilities, and branch/jump/switch/return terminators.
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
_CHECKED_HELPERS = {
    "+": "merit_checked_add_i64",
    "-": "merit_checked_sub_i64",
    "*": "merit_checked_mul_i64",
    "/": "merit_checked_div_i64",
    "%": "merit_checked_rem_i64",
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
        if value == -(2**63):
            return "INT64_MIN"
        if not -(2**63) <= value <= 2**63 - 1:
            raise MirToCError(f"i64 constant is out of range: {value}")
        return f"INT64_C({value})"
    raise MirToCError(f"unsupported MIR constant for C emission: {value!r}")


def _local(local_id: int) -> str:
    return f"m{local_id}"


def _function_table(module: MirModule) -> dict[str, MirFunction]:
    table = {function.name: function for function in module.functions}
    c_names: dict[str, str] = {}
    for function in module.functions:
        c_name = _identifier(function.name)
        previous = c_names.get(c_name)
        if previous is not None and previous != function.name:
            raise MirToCError(
                f"MIR function names {previous!r} and {function.name!r} collide as C identifier {c_name!r}"
            )
        c_names[c_name] = function.name
    return table


def _instruction(instruction: MirInstruction, functions: dict[str, MirFunction]) -> list[str]:
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
        if instruction.numeric_policy == "checked" and instruction.symbol in _CHECKED_HELPERS:
            helper = _CHECKED_HELPERS[instruction.symbol]
            return [f"{result} = {helper}({operands[0]}, {operands[1]});"]
        if instruction.numeric_policy not in {"exact", "floating"}:
            raise MirToCError(f"numeric policy not supported by core C emission: {instruction.numeric_policy}")
        return [f"{result} = {operands[0]} {_BINARY[instruction.symbol]} {operands[1]};"]
    if kind == "convert":
        if result is None or len(operands) != 1:
            raise MirToCError("convert instruction requires one operand and a result")
        if instruction.conversion_policy not in {"exact", "checked"}:
            raise MirToCError(f"conversion policy not supported by core C emission: {instruction.conversion_policy}")
        return [f"{result} = {operands[0]};"]
    if kind == "call":
        if not instruction.symbol:
            raise MirToCError("call instruction requires a resolved symbol")
        callee = functions.get(instruction.symbol)
        if callee is None:
            raise MirToCError(f"call references unknown MIR function: {instruction.symbol}")
        if operands:
            raise MirToCError("core C emitter currently supports only no-argument MIR calls")
        callee_type = _type(callee.return_type)
        call = f"{_identifier(callee.name)}()"
        if callee_type == "void":
            if result is not None:
                raise MirToCError("unit-returning MIR calls cannot produce a result local")
            return [f"{call};"]
        if result is None:
            raise MirToCError("value-returning MIR calls require a result local")
        return [f"{result} = {call};"]
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
        return [
            f"if ({_local(terminator.operands[0])}) goto b{terminator.targets[0]};",
            f"goto b{terminator.targets[1]};",
        ]
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


def _prototype(function: MirFunction) -> str:
    return f"{_type(function.return_type)} {_identifier(function.name)}(void);"


def emit_c_function(function: MirFunction, functions: dict[str, MirFunction] | None = None) -> str:
    functions = functions or {function.name: function}
    return_type = _type(function.return_type)
    lines = [f"{return_type} {_identifier(function.name)}(void) {{"]
    for local in function.locals:
        local_type = _type(local.type)
        if local_type == "void":
            raise MirToCError("MIR locals cannot have unit type in core C emission")
        lines.append(f"    {local_type} {_local(local.local_id)} = 0;")
    lines.append(f"    goto b{function.entry_block};")
    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _instruction(instruction, functions):
                lines.append(f"    {statement}")
        for statement in _terminator(block.terminator, return_type):
            lines.append(f"    {statement}")
    lines.append("}")
    return "\n".join(lines)


def _checked_helpers(operators: set[str]) -> list[str]:
    if not operators:
        return []
    lines = [
        "static void merit_numeric_failure(const char *operation) { (void)operation; abort(); }",
    ]
    if "+" in operators:
        lines.extend([
            "static int64_t merit_checked_add_i64(int64_t a, int64_t b) {",
            "    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) merit_numeric_failure(\"add\");",
            "    return a + b;",
            "}",
        ])
    if "-" in operators:
        lines.extend([
            "static int64_t merit_checked_sub_i64(int64_t a, int64_t b) {",
            "    if ((b > 0 && a < INT64_MIN + b) || (b < 0 && a > INT64_MAX + b)) merit_numeric_failure(\"sub\");",
            "    return a - b;",
            "}",
        ])
    if "*" in operators:
        lines.extend([
            "static int64_t merit_checked_mul_i64(int64_t a, int64_t b) {",
            "    if (a == 0 || b == 0) return 0;",
            "    if ((a == INT64_MIN && b == -1) || (b == INT64_MIN && a == -1)) merit_numeric_failure(\"mul\");",
            "    if (a > 0) {",
            "        if ((b > 0 && a > INT64_MAX / b) || (b < 0 && b < INT64_MIN / a)) merit_numeric_failure(\"mul\");",
            "    } else {",
            "        if ((b > 0 && a < INT64_MIN / b) || (b < 0 && a < INT64_MAX / b)) merit_numeric_failure(\"mul\");",
            "    }",
            "    return a * b;",
            "}",
        ])
    if "/" in operators:
        lines.extend([
            "static int64_t merit_checked_div_i64(int64_t a, int64_t b) {",
            "    if (b == 0 || (a == INT64_MIN && b == -1)) merit_numeric_failure(\"div\");",
            "    return a / b;",
            "}",
        ])
    if "%" in operators:
        lines.extend([
            "static int64_t merit_checked_rem_i64(int64_t a, int64_t b) {",
            "    if (b == 0 || (a == INT64_MIN && b == -1)) merit_numeric_failure(\"rem\");",
            "    return a % b;",
            "}",
        ])
    return lines


def emit_c_module(module: MirModule) -> str:
    functions = _function_table(module)
    instructions = [
        instruction
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    needs_contract = any(instruction.kind == "contract_check" for instruction in instructions)
    needs_capability = any(instruction.kind == "capability_check" for instruction in instructions)
    checked_operators = {
        instruction.symbol
        for instruction in instructions
        if instruction.kind == "binary"
        and instruction.numeric_policy == "checked"
        and instruction.symbol in _CHECKED_HELPERS
    }
    prelude = [
        "/* generated from bootstrap-mir-v1; deterministic, do not edit */",
        "#include <stdbool.h>",
        "#include <stdint.h>",
        "#include <stdlib.h>",
        "",
    ]
    runtime = _checked_helpers(checked_operators)
    if needs_contract:
        runtime.append("static void merit_contract_failure(const char *kind) { (void)kind; abort(); }")
    if needs_capability:
        runtime.append("static void merit_capability_check(const char *capability) { (void)capability; }")
    if runtime:
        prelude.extend([*runtime, ""])
    prototypes = [_prototype(function) for function in module.functions]
    if prototypes:
        prelude.extend([*prototypes, ""])
    emitted = "\n\n".join(emit_c_function(function, functions) for function in module.functions)
    return "\n".join([*prelude, emitted, ""])
