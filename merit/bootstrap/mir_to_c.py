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
_COPY_PAYLOAD_ENUM_PREFIX = "enum_copy_payload_"
_I64_STRUCT_PREFIX = "struct_i64_"
_DESTRUCTOR_I64_STRUCT_PREFIX = "struct_i64_destructor_"
_OWNED_PAYLOAD_ENUM_PREFIX = "enum_owned_payload_"
_ENUM_VARIANT_PREFIX = "variant_"
_STRUCT_FIELD_PREFIX = "field_"


def _copy_payload_enum_identity(type_: MirType) -> str | None:
    if type_.arguments or not type_.name.startswith(_COPY_PAYLOAD_ENUM_PREFIX):
        return None
    identity = type_.name[len(_COPY_PAYLOAD_ENUM_PREFIX):]
    if not identity or not identity.isdecimal():
        raise MirToCError(f"invalid Copy-payload enum MIR type: {type_.name}")
    return identity


def _i64_struct_identity(type_: MirType) -> str | None:
    if type_.arguments or not type_.name.startswith(_I64_STRUCT_PREFIX) or type_.name.startswith(_DESTRUCTOR_I64_STRUCT_PREFIX):
        return None
    identity = type_.name[len(_I64_STRUCT_PREFIX):]
    if not identity or not identity.isdecimal():
        raise MirToCError(f"invalid single-i64 struct MIR type: {type_.name}")
    return identity


def _destructor_i64_struct_identity(type_: MirType) -> str | None:
    if type_.arguments or not type_.name.startswith(_DESTRUCTOR_I64_STRUCT_PREFIX):
        return None
    identity = type_.name[len(_DESTRUCTOR_I64_STRUCT_PREFIX):]
    if not identity or not identity.isdecimal():
        raise MirToCError(f"invalid destructor single-i64 struct MIR type: {type_.name}")
    return identity


def _owned_payload_enum_identity(type_: MirType) -> tuple[str, str] | None:
    if type_.arguments or not type_.name.startswith(_OWNED_PAYLOAD_ENUM_PREFIX):
        return None
    identity = type_.name[len(_OWNED_PAYLOAD_ENUM_PREFIX):]
    parts = identity.split("_")
    if len(parts) != 2 or not all(part and part.isdecimal() for part in parts):
        raise MirToCError(f"invalid owned-payload enum MIR type: {type_.name}")
    return parts[0], parts[1]


def _identifier(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "merit_" + cleaned
    return cleaned


def _type(type_: MirType) -> str:
    enum_identity = _copy_payload_enum_identity(type_)
    if enum_identity is not None:
        return f"merit_enum_copy_payload_{enum_identity}"
    struct_identity = _i64_struct_identity(type_)
    if struct_identity is not None:
        return f"merit_struct_i64_{struct_identity}"
    destructor_identity = _destructor_i64_struct_identity(type_)
    if destructor_identity is not None:
        return f"merit_struct_i64_destructor_{destructor_identity}"
    owned_enum_identity = _owned_payload_enum_identity(type_)
    if owned_enum_identity is not None:
        enum_identity, payload_identity = owned_enum_identity
        return f"merit_enum_owned_payload_{enum_identity}_{payload_identity}"
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


def _instruction(
    instruction: MirInstruction,
    functions: dict[str, MirFunction],
    local_types: dict[int, MirType] | None = None,
) -> list[str]:
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
    if kind == "construct":
        if result is None or len(operands) != 1 or not instruction.symbol:
            raise MirToCError("aggregate construction requires one value and a constructor symbol")
        if local_types is None or instruction.result not in local_types:
            raise MirToCError("aggregate construction requires a resolved result type")
        result_type = local_types[instruction.result]
        struct_identity = _i64_struct_identity(result_type)
        if struct_identity is None:
            struct_identity = _destructor_i64_struct_identity(result_type)
        if struct_identity is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("single-i64 struct construction requires field_0")
            return [f"{result} = ({_type(result_type)}) {{ {operands[0]} }};"]
        if _copy_payload_enum_identity(result_type) is None and _owned_payload_enum_identity(result_type) is None:
            raise MirToCError("core C emission only supports represented aggregate construction")
        if not instruction.symbol.startswith(_ENUM_VARIANT_PREFIX):
            raise MirToCError("Copy-payload enum construction has an invalid variant symbol")
        ordinal = instruction.symbol[len(_ENUM_VARIANT_PREFIX):]
        if not ordinal or not ordinal.isdecimal():
            raise MirToCError("Copy-payload enum construction has an invalid variant ordinal")
        return [f"{result} = ({_type(local_types[instruction.result])}) {{ INT64_C({ordinal}), {operands[0]} }};"]
    if kind == "load_field":
        if result is None or len(operands) != 1 or not instruction.symbol:
            raise MirToCError("aggregate field load requires one receiver and a field symbol")
        if local_types is None or instruction.operands[0] not in local_types:
            raise MirToCError("aggregate field load requires a resolved receiver type")
        receiver_type = local_types[instruction.operands[0]]
        if _i64_struct_identity(receiver_type) is not None or _destructor_i64_struct_identity(receiver_type) is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("single-i64 struct field load requires field_0")
            return [f"{result} = {operands[0]}.field_0;"]
        if (
            _copy_payload_enum_identity(receiver_type) is None
            and _owned_payload_enum_identity(receiver_type) is None
        ) or instruction.symbol not in {"tag", "payload"}:
            raise MirToCError("core C emission only supports represented aggregate fields")
        return [f"{result} = {operands[0]}.{instruction.symbol};"]
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
    if kind == "print":
        if result is not None or len(operands) != 1:
            raise MirToCError("print instruction requires one operand and no result")
        return [f'printf("%lld\\n", (long long){operands[0]});']
    if kind == "drop":
        if len(operands) != 1:
            raise MirToCError("drop instruction requires one operand")
        if local_types is not None and instruction.operands[0] in local_types:
            operand_type = local_types[instruction.operands[0]]
            if _destructor_i64_struct_identity(operand_type) is not None:
                return [f'printf("%lld\\n", (long long){operands[0]}.field_0);']
            if _owned_payload_enum_identity(operand_type) is not None:
                return [f'printf("%lld\\n", (long long){operands[0]}.payload.field_0);']
            if _i64_struct_identity(operand_type) is not None:
                return [f"/* deterministic drop of non-copy aggregate {operands[0]} */"]
        return ["/* explicit no-op in scalar bootstrap C subset */"]
    if kind in {"deallocate", "nop"}:
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
    local_types = {local.local_id: local.type for local in function.locals}
    for local in function.locals:
        local_type = _type(local.type)
        if local_type == "void":
            raise MirToCError("MIR locals cannot have unit type in core C emission")
        initializer = "{0}" if (
            _copy_payload_enum_identity(local.type) is not None
            or _i64_struct_identity(local.type) is not None
            or _destructor_i64_struct_identity(local.type) is not None
            or _owned_payload_enum_identity(local.type) is not None
        ) else "0"
        lines.append(f"    {local_type} {_local(local.local_id)} = {initializer};")
    lines.append(f"    goto b{function.entry_block};")
    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _instruction(instruction, functions, local_types):
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
    needs_print = any(instruction.kind == "print" for instruction in instructions) or any(
        _destructor_i64_struct_identity(local.type) is not None
        or _owned_payload_enum_identity(local.type) is not None
        for function in module.functions for local in function.locals
    )
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
        *(["#include <stdio.h>"] if needs_print else []),
        "#include <stdlib.h>",
        "",
    ]
    enum_identities = sorted({
        identity
        for function in module.functions
        for local in function.locals
        if (identity := _copy_payload_enum_identity(local.type)) is not None
    }, key=int)
    if enum_identities:
        prelude.extend([
            *[
                f"typedef struct {{ int64_t tag; int64_t payload; }} merit_enum_copy_payload_{identity};"
                for identity in enum_identities
            ],
            "",
        ])
    struct_identities = sorted({
        identity
        for function in module.functions
        for local in function.locals
        if (identity := _i64_struct_identity(local.type)) is not None
    }, key=int)
    if struct_identities:
        prelude.extend([
            *[
                f"typedef struct {{ int64_t field_0; }} merit_struct_i64_{identity};"
                for identity in struct_identities
            ],
            "",
        ])
    destructor_struct_identities = sorted({
        identity
        for function in module.functions
        for local in function.locals
        if (identity := _destructor_i64_struct_identity(local.type)) is not None
    }, key=int)
    if destructor_struct_identities:
        prelude.extend([
            *[
                f"typedef struct {{ int64_t field_0; }} merit_struct_i64_destructor_{identity};"
                for identity in destructor_struct_identities
            ],
            "",
        ])
    owned_enum_identities = sorted({
        identity
        for function in module.functions
        for local in function.locals
        if (identity := _owned_payload_enum_identity(local.type)) is not None
    }, key=lambda identity: (int(identity[0]), int(identity[1])))
    if owned_enum_identities:
        prelude.extend([
            *[
                "typedef struct { int64_t tag; "
                f"merit_struct_i64_destructor_{payload_identity} payload; "
                f"}} merit_enum_owned_payload_{enum_identity}_{payload_identity};"
                for enum_identity, payload_identity in owned_enum_identities
            ],
            "",
        ])
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
