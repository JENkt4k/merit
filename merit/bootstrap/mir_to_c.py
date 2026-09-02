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

from merit.bootstrap.mir_contract import MirDestructor, MirFunction, MirInstruction, MirModule, MirTerminator, MirType


class MirToCError(ValueError):
    """Raised when MIR is outside the supported deterministic C subset."""


_C_TYPES = {
    "i64": "int64_t", "bool": "bool", "unit": "void",
    "Allocator": "merit_Allocator", "Buffer": "merit_Buffer",
    "i8": "int8_t", "i16": "int16_t", "i32": "int32_t",
    "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
    "String": "merit_String", "ByteSlice": "merit_ByteSlice",
}
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
_INTEGER_TYPES = frozenset({"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"})
_COPY_PAYLOAD_ENUM_PREFIX = "enum_copy_payload_"
_I64_STRUCT_PREFIX = "struct_i64_"
_DESTRUCTOR_I64_STRUCT_PREFIX = "struct_i64_destructor_"
_OWNED_PAYLOAD_ENUM_PREFIX = "enum_owned_payload_"
_OWNED_FIELD_STRUCT_PREFIX = "struct_owned_field_"
_AGGREGATE_STRUCT_PREFIX = "struct_aggregate_"
_ENUM_VARIANT_PREFIX = "variant_"
_STRUCT_FIELD_PREFIX = "field_"
_VECTOR_OPERATIONS = frozenset({
    "new", "push", "len", "get", "set", "replace", "pop", "drop", "transfer", "allocator",
})


def _vector_type(type_: MirType) -> MirType | None:
    if type_.name != "Vec":
        return None
    if len(type_.arguments) != 1:
        raise MirToCError("Vec MIR types require exactly one element type")
    return type_.arguments[0]


def _type_mangle(type_: MirType) -> str:
    name = type_.name.encode("utf-8").hex()
    if not type_.arguments:
        return name
    return name + "_a_" + "_z_".join(_type_mangle(argument) for argument in type_.arguments)


def _vector_c_name(type_: MirType) -> str:
    element = _vector_type(type_)
    if element is None:
        raise MirToCError(f"not a vector MIR type: {type_.name}")
    return f"merit_Vec_{_type_mangle(element)}"


def _vector_runtime_name(type_: MirType, operation: str) -> str:
    if operation not in _VECTOR_OPERATIONS:
        raise MirToCError(f"unsupported vector operation: {operation}")
    return f"merit_vec_{operation}_{_type_mangle(_vector_type(type_) or type_)}"


def _vector_call_operation(symbol: str) -> str | None:
    match = re.fullmatch(r"vec_(new|push|len|get|set|replace|pop|drop|transfer|allocator)__.+", symbol)
    return None if match is None else match.group(1)


def _decimal_type(type_: MirType) -> tuple[int, int, int, int] | None:
    if type_.arguments:
        return None
    match = re.fullmatch(r"decimal_(\d+)_(\d+)_(\d+)_([0-4])", type_.name)
    if match is None:
        return None
    identity, precision, scale, policy = map(int, match.groups())
    if precision < 1 or scale > precision:
        raise MirToCError(f"invalid decimal MIR type: {type_.name}")
    return identity, precision, scale, policy


def _bounded_type(type_: MirType) -> tuple[int, int, int, int, MirType] | None:
    match = re.fullmatch(r"bounded_(\d+)_(\d+)_(-?\d+)_(-?\d+)", type_.name)
    if match is None:
        return None
    if len(type_.arguments) != 1 or type_.arguments[0].name not in _INTEGER_TYPES:
        raise MirToCError(f"invalid bounded MIR type: {type_.name}")
    identity, base_code, minimum, maximum = map(int, match.groups())
    if minimum > maximum:
        raise MirToCError(f"invalid bounded MIR type: {type_.name}")
    return identity, base_code, minimum, maximum, type_.arguments[0]


def _int128_literal(value: int) -> str:
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    high, low = divmod(magnitude, 1_000_000_000_000_000_000)
    expression = f"((__int128){high} * INT64_C(1000000000000000000) + INT64_C({low}))"
    return f"-{expression}" if sign else expression


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


def _owned_field_struct_identity(type_: MirType) -> tuple[str, MirType] | None:
    if not type_.name.startswith(_OWNED_FIELD_STRUCT_PREFIX):
        return None
    identity = type_.name[len(_OWNED_FIELD_STRUCT_PREFIX):]
    if not identity or not identity.isdecimal() or len(type_.arguments) != 1:
        raise MirToCError(f"invalid owned-field struct MIR type: {type_.name}")
    return identity, type_.arguments[0]


def _recursive_owned_payload_enum_identity(type_: MirType) -> tuple[str, tuple[MirType, ...]] | None:
    if not type_.name.startswith(_OWNED_PAYLOAD_ENUM_PREFIX) or not type_.arguments:
        return None
    identity = type_.name[len(_OWNED_PAYLOAD_ENUM_PREFIX):]
    if not identity or not identity.isdecimal() or not type_.arguments:
        raise MirToCError(f"invalid recursive owned-payload enum MIR type: {type_.name}")
    return identity, type_.arguments


def _aggregate_struct_identity(type_: MirType) -> tuple[str, tuple[MirType, ...], int | None] | None:
    if not type_.name.startswith(_AGGREGATE_STRUCT_PREFIX):
        return None
    match = re.fullmatch(r"struct_aggregate_(\d+)_destructor_(-1|\d+)", type_.name)
    if match is None or not type_.arguments:
        raise MirToCError(f"invalid aggregate struct MIR type: {type_.name}")
    policy = int(match.group(2))
    if policy >= len(type_.arguments):
        raise MirToCError(f"aggregate struct destructor field is outside schema: {type_.name}")
    return match.group(1), type_.arguments, None if policy < 0 else policy


def _identifier(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "merit_" + cleaned
    return cleaned


def _type(type_: MirType) -> str:
    if _vector_type(type_) is not None:
        return _vector_c_name(type_)
    decimal = _decimal_type(type_)
    if decimal is not None:
        return "int64_t" if decimal[1] <= 18 else "__int128"
    bounded = _bounded_type(type_)
    if bounded is not None:
        return _type(bounded[4])
    aggregate = _aggregate_struct_identity(type_)
    if aggregate is not None:
        return f"merit_struct_aggregate_{aggregate[0]}"
    owned_struct = _owned_field_struct_identity(type_)
    if owned_struct is not None:
        return f"merit_struct_owned_field_{owned_struct[0]}"
    recursive_enum = _recursive_owned_payload_enum_identity(type_)
    if recursive_enum is not None:
        return f"merit_enum_owned_payload_{recursive_enum[0]}"
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


def _literal(value: object, type_: MirType) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type_ == MirType("bool") and isinstance(value, int):
        if value == 1:
            return "true"
        if value == 0:
            return "false"
        raise MirToCError(f"boolean integer constant must be 0 or 1, got {value}")
    if isinstance(value,str) and type_==MirType("String"):
        encoded=value.encode("utf-8")
        bytes_literal="".join(f"\\x{byte:02x}" for byte in encoded)
        return f'(merit_String){{ (const uint8_t *)"{bytes_literal}", {len(encoded)} }}'
    if isinstance(value, int):
        decimal = _decimal_type(type_)
        if decimal is not None:
            limit = 10 ** decimal[1] - 1
            if abs(value) > limit:
                raise MirToCError(f"decimal constant is out of range: {value}")
            return f"INT64_C({value})" if decimal[1] <= 18 else _int128_literal(value)
        bounded = _bounded_type(type_)
        if bounded is not None:
            if not bounded[2] <= value <= bounded[3]:
                raise MirToCError(f"bounded constant is out of range: {value}")
            return _literal(value, bounded[4])
        if type_.arguments or type_.name not in _INTEGER_TYPES:
            raise MirToCError(f"integer constant has unsupported MIR type: {type_.name}")
        signed = type_.name.startswith("i")
        bits = int(type_.name[1:])
        minimum = -(2 ** (bits - 1)) if signed else 0
        maximum = 2 ** (bits - (1 if signed else 0)) - 1
        if not minimum <= value <= maximum:
            raise MirToCError(f"{type_.name} constant is out of range: {value}")
        if signed and value == minimum:
            return f"INT{bits}_MIN"
        macro = f"INT{bits}_C" if signed else f"UINT{bits}_C"
        return f"{macro}({value})"
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


def _destructor_c_name(type_: MirType) -> str:
    return f"merit_custom_destructor_{_identifier(_type(type_))}"


def _drop_statements(
    expression: str, type_: MirType, destructors: dict[MirType, MirDestructor]
) -> list[str]:
    if _vector_type(type_) is not None:
        return [f"{_vector_runtime_name(type_, 'drop')}(&({expression}));"]
    if type_.name == "Buffer" and not type_.arguments:
        return [f"merit_buffer_drop(&({expression}));"]
    aggregate = _aggregate_struct_identity(type_)
    if aggregate is not None:
        _, fields, destructor_field = aggregate
        statements: list[str] = []
        if type_ in destructors:
            statements.append(f"{_destructor_c_name(type_)}(&({expression}));")
        elif destructor_field is not None:
            statements.append(
                f'printf("%lld\\n", (long long){expression}.field_{destructor_field});'
            )
        for ordinal, field_type in enumerate(fields):
            statements.extend(_drop_statements(f"{expression}.field_{ordinal}", field_type, destructors))
        return statements
    if _destructor_i64_struct_identity(type_) is not None:
        if type_ in destructors:
            return [f"{_destructor_c_name(type_)}(&({expression}));"]
        return [f'printf("%lld\\n", (long long){expression}.field_0);']
    owned_struct = _owned_field_struct_identity(type_)
    if owned_struct is not None:
        return _drop_statements(f"{expression}.field_0", owned_struct[1], destructors)
    recursive_enum = _recursive_owned_payload_enum_identity(type_)
    if recursive_enum is not None:
        statements = [f"switch ({expression}.tag) {{"]
        for ordinal, payload in enumerate(recursive_enum[1]):
            cleanup = _drop_statements(
                f"{expression}.payload.variant_{ordinal}", payload, destructors
            )
            statements.append(f"case INT64_C({ordinal}):")
            statements.extend(f"    {line}" for line in cleanup)
            statements.append("    break;")
        statements.extend(["default: abort();", "}"])
        return statements
    if _owned_payload_enum_identity(type_) is not None:
        return [f'printf("%lld\\n", (long long){expression}.payload.field_0);']
    if _i64_struct_identity(type_) is not None:
        return [f"/* deterministic drop of non-copy aggregate {expression} */"]
    return ["/* explicit no-op in scalar bootstrap C subset */"]


def _vector_depth(type_: MirType) -> int:
    element = _vector_type(type_)
    if element is None:
        return 0
    return 1 + _vector_depth(element)


def _vector_runtime(
    vector_types: tuple[MirType, ...], destructors: dict[MirType, MirDestructor]
) -> list[str]:
    lines: list[str] = []
    for vector_type in sorted(vector_types, key=lambda item: (_vector_depth(item), _type_mangle(item))):
        element = _vector_type(vector_type)
        assert element is not None
        vector_c = _type(vector_type)
        element_c = _type(element)
        reserve = f"merit_vec_reserve_{_type_mangle(element)}"
        new = _vector_runtime_name(vector_type, "new")
        push = _vector_runtime_name(vector_type, "push")
        length = _vector_runtime_name(vector_type, "len")
        get = _vector_runtime_name(vector_type, "get")
        set_ = _vector_runtime_name(vector_type, "set")
        replace = _vector_runtime_name(vector_type, "replace")
        pop = _vector_runtime_name(vector_type, "pop")
        drop = _vector_runtime_name(vector_type, "drop")
        transfer = _vector_runtime_name(vector_type, "transfer")
        allocator = _vector_runtime_name(vector_type, "allocator")
        element_at = f"(({element_c} *)value->data)[index]"
        lines.extend([
            f"static void {reserve}({vector_c} *value, size_t needed) {{",
            "    if (needed <= value->capacity) return;",
            "    size_t capacity = value->capacity ? value->capacity : 8;",
            "    while (capacity < needed) capacity *= 2;",
            f"    void *data = realloc(value->data, capacity * sizeof({element_c}));",
            '    if (!data) { fprintf(stderr, "Merit allocation failed\\n"); exit(80); }',
            "    value->data = data; value->capacity = capacity;",
            "}",
            f"static {vector_c} {new}(merit_Allocator allocator, int64_t capacity) {{",
            '    if (capacity < 0) { fprintf(stderr, "Merit negative capacity\\n"); exit(81); }',
            f"    {vector_c} result = {{0}}; result.allocator = allocator; {reserve}(&result, (size_t)capacity);",
            "    return result;",
            "}",
            f"static void {push}({vector_c} *value, {element_c} element) {{",
            f"    {reserve}(value, value->len + 1); (({element_c} *)value->data)[value->len++] = element;",
            "}",
            f"static int64_t {length}(const {vector_c} *value) {{ return (int64_t)value->len; }}",
            f"static merit_Allocator {allocator}(const {vector_c} *value) {{ return value->allocator; }}",
            f"static {element_c} {get}(const {vector_c} *value, int64_t index) {{",
            '    if (index < 0 || (size_t)index >= value->len) { fprintf(stderr, "Merit vector index out of bounds\\n"); exit(86); }',
            f"    return ((const {element_c} *)value->data)[index];",
            "}",
            f"static void {set_}({vector_c} *value, int64_t index, {element_c} element) {{",
            '    if (index < 0 || (size_t)index >= value->len) { fprintf(stderr, "Merit vector index out of bounds\\n"); exit(86); }',
            f"    (({element_c} *)value->data)[index] = element;",
            "}",
            f"static void {replace}({vector_c} *value, int64_t index, {element_c} element) {{",
            '    if (index < 0 || (size_t)index >= value->len) { fprintf(stderr, "Merit vector index out of bounds\\n"); exit(86); }',
            *[f"    {statement}" for statement in _drop_statements(element_at, element, destructors)],
            f"    (({element_c} *)value->data)[index] = element;",
            "}",
            f"static {element_c} {pop}({vector_c} *value) {{",
            '    if (!value->len) { fprintf(stderr, "Merit vector pop from empty\\n"); exit(86); }',
            f"    return (({element_c} *)value->data)[--value->len];",
            "}",
            f"static void {drop}({vector_c} *value) {{",
            "    for (size_t index = 0; index < value->len; ++index) {",
            *[f"        {statement}" for statement in _drop_statements(element_at, element, destructors)],
            "    }",
            "    free(value->data); value->data = NULL; value->len = 0; value->capacity = 0;",
            "}",
            f"static void {transfer}({vector_c} *destination, {vector_c} *source) {{",
            '    if (destination == source) { fprintf(stderr, "Merit vector transfer aliases itself\\n"); exit(90); }',
            '    if (!merit_allocator_compatible(destination->allocator, source->allocator)) { fprintf(stderr, "Merit incompatible vector allocators\\n"); exit(90); }',
            '    if (destination->len) { fprintf(stderr, "Merit vector transfer destination is not empty\\n"); exit(90); }',
            "    free(destination->data); destination->data = source->data; destination->len = source->len; destination->capacity = source->capacity;",
            "    source->data = NULL; source->len = 0; source->capacity = 0;",
            "}",
        ])
    return lines


def _instruction(
    instruction: MirInstruction,
    functions: dict[str, MirFunction],
    local_types: dict[int, MirType] | None = None,
    local_ownership: dict[int, str] | None = None,
    destructors: dict[MirType, MirDestructor] | None = None,
) -> list[str]:
    destructors = destructors or {}
    local_ownership = local_ownership or {}
    result = _local(instruction.result) if instruction.result is not None else None
    operands = [_local(value) for value in instruction.operands]
    kind = instruction.kind
    if kind == "const":
        if result is None:
            raise MirToCError("const instruction requires a result")
        if local_types is None or instruction.result not in local_types:
            raise MirToCError("const instruction requires a resolved result type")
        return [f"{result} = {_literal(instruction.value, local_types[instruction.result])};"]
    if kind in {"copy", "move", "borrow"}:
        if result is None or len(operands) != 1:
            raise MirToCError(f"{kind} instruction requires one operand and a result")
        source = operands[0]
        if kind == "borrow" and local_ownership.get(instruction.operands[0], "value") not in {"borrowed", "mutable_borrow"}:
            source = f"&{source}"
        return [f"{result} = {source};"]
    if kind == "construct":
        if result is None or len(operands) != 1 or not instruction.symbol:
            raise MirToCError("aggregate construction requires one value and a constructor symbol")
        if local_types is None or instruction.result not in local_types:
            raise MirToCError("aggregate construction requires a resolved result type")
        result_type = local_types[instruction.result]
        aggregate = _aggregate_struct_identity(result_type)
        if aggregate is not None:
            _, fields, _ = aggregate
            if not instruction.symbol.startswith(_STRUCT_FIELD_PREFIX):
                raise MirToCError("aggregate construction requires a field symbol")
            ordinal_text = instruction.symbol[len(_STRUCT_FIELD_PREFIX):]
            if not ordinal_text.isdecimal() or int(ordinal_text) >= len(fields):
                raise MirToCError("aggregate construction field is outside schema")
            return [f"{result} = ({_type(result_type)}) {{ .{instruction.symbol} = {operands[0]} }};"]
        struct_identity = _i64_struct_identity(result_type)
        if struct_identity is None:
            struct_identity = _destructor_i64_struct_identity(result_type)
        if struct_identity is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("single-i64 struct construction requires field_0")
            return [f"{result} = ({_type(result_type)}) {{ {operands[0]} }};"]
        if _owned_field_struct_identity(result_type) is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("owned-field struct construction requires field_0")
            return [f"{result} = ({_type(result_type)}) {{ {operands[0]} }};"]
        if (
            _copy_payload_enum_identity(result_type) is None
            and _owned_payload_enum_identity(result_type) is None
            and _recursive_owned_payload_enum_identity(result_type) is None
        ):
            raise MirToCError("core C emission only supports represented aggregate construction")
        if not instruction.symbol.startswith(_ENUM_VARIANT_PREFIX):
            raise MirToCError("Copy-payload enum construction has an invalid variant symbol")
        ordinal = instruction.symbol[len(_ENUM_VARIANT_PREFIX):]
        if not ordinal or not ordinal.isdecimal():
            raise MirToCError("Copy-payload enum construction has an invalid variant ordinal")
        if (recursive := _recursive_owned_payload_enum_identity(result_type)) is not None:
            ordinal_value = int(ordinal)
            if ordinal_value >= len(recursive[1]):
                raise MirToCError("owned-payload enum constructor is outside schema")
            return [
                f"{result} = ({_type(result_type)}) {{ .tag = INT64_C({ordinal}), "
                f".payload.variant_{ordinal} = {operands[0]} }};"
            ]
        return [f"{result} = ({_type(local_types[instruction.result])}) {{ INT64_C({ordinal}), {operands[0]} }};"]
    if kind == "load_field":
        if result is None or len(operands) != 1 or not instruction.symbol:
            raise MirToCError("aggregate field load requires one receiver and a field symbol")
        if local_types is None or instruction.operands[0] not in local_types:
            raise MirToCError("aggregate field load requires a resolved receiver type")
        receiver_type = local_types[instruction.operands[0]]
        aggregate = _aggregate_struct_identity(receiver_type)
        if aggregate is not None:
            _, fields, _ = aggregate
            if not instruction.symbol.startswith(_STRUCT_FIELD_PREFIX):
                raise MirToCError("aggregate field load requires a field symbol")
            ordinal_text = instruction.symbol[len(_STRUCT_FIELD_PREFIX):]
            if not ordinal_text.isdecimal() or int(ordinal_text) >= len(fields):
                raise MirToCError("aggregate field load is outside schema")
            access = "->" if local_ownership.get(instruction.operands[0]) in {"borrowed", "mutable_borrow"} else "."
            return [f"{result} = {operands[0]}{access}{instruction.symbol};"]
        if _i64_struct_identity(receiver_type) is not None or _destructor_i64_struct_identity(receiver_type) is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("single-i64 struct field load requires field_0")
            access = "->" if local_ownership.get(instruction.operands[0]) in {"borrowed", "mutable_borrow"} else "."
            return [f"{result} = {operands[0]}{access}field_0;"]
        if _owned_field_struct_identity(receiver_type) is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("owned-field struct field load requires field_0")
            access = "->" if local_ownership.get(instruction.operands[0]) in {"borrowed", "mutable_borrow"} else "."
            return [f"{result} = {operands[0]}{access}field_0;"]
        if (
            _copy_payload_enum_identity(receiver_type) is None
            and _owned_payload_enum_identity(receiver_type) is None
            and _recursive_owned_payload_enum_identity(receiver_type) is None
        ) or not (
            instruction.symbol == "tag"
            or instruction.symbol == "payload"
            or instruction.symbol.startswith("payload_")
        ):
            raise MirToCError("core C emission only supports represented aggregate fields")
        access = "->" if local_ownership.get(instruction.operands[0]) in {"borrowed", "mutable_borrow"} else "."
        recursive = _recursive_owned_payload_enum_identity(receiver_type)
        if recursive is not None and instruction.symbol.startswith("payload_"):
            ordinal_text = instruction.symbol.removeprefix("payload_")
            if not ordinal_text.isdecimal() or int(ordinal_text) >= len(recursive[1]):
                raise MirToCError("enum payload variant is outside schema")
            ordinal = int(ordinal_text)
            if instruction.result not in local_types or local_types[instruction.result] != recursive[1][ordinal]:
                raise MirToCError("enum payload result type disagrees with variant schema")
            return [f"{result} = {operands[0]}{access}payload.variant_{ordinal};"]
        if instruction.symbol.startswith("payload_"):
            return [f"{result} = {operands[0]}{access}payload;"]
        return [f"{result} = {operands[0]}{access}{instruction.symbol};"]
    if kind == "store_field":
        if result is None or len(operands) != 1 or not instruction.symbol:
            raise MirToCError("aggregate field store requires one value, a receiver result, and a field symbol")
        if local_types is None or instruction.result not in local_types:
            raise MirToCError("aggregate field store requires a resolved receiver type")
        receiver_type = local_types[instruction.result]
        if (
            _i64_struct_identity(receiver_type) is not None
            or _destructor_i64_struct_identity(receiver_type) is not None
        ):
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("single-i64 struct field store requires field_0")
            access = "->" if local_ownership.get(instruction.result) == "mutable_borrow" else "."
            return [f"{result}{access}field_0 = {operands[0]};"]
        owned_struct = _owned_field_struct_identity(receiver_type)
        if owned_struct is not None:
            if instruction.symbol != f"{_STRUCT_FIELD_PREFIX}0":
                raise MirToCError("owned-field struct field store requires field_0")
            access = "->" if local_ownership.get(instruction.result) == "mutable_borrow" else "."
            assignment = f"{result}{access}field_0 = {operands[0]};"
            if instruction.ownership == "moved":
                return [*_drop_statements(f"{result}{access}field_0", owned_struct[1], destructors), assignment]
            return [assignment]
        aggregate = _aggregate_struct_identity(receiver_type)
        if aggregate is None:
            raise MirToCError("field stores are only supported for represented aggregate structs")
        _, fields, _ = aggregate
        if not instruction.symbol.startswith(_STRUCT_FIELD_PREFIX):
            raise MirToCError("aggregate field store requires a field symbol")
        ordinal_text = instruction.symbol[len(_STRUCT_FIELD_PREFIX):]
        if not ordinal_text.isdecimal() or int(ordinal_text) >= len(fields):
            raise MirToCError("aggregate field store is outside schema")
        access = "->" if local_ownership.get(instruction.result) == "mutable_borrow" else "."
        assignment = f"{result}{access}{instruction.symbol} = {operands[0]};"
        if instruction.ownership == "moved":
            field_type = fields[int(ordinal_text)][1]
            return [*_drop_statements(f"{result}{access}{instruction.symbol}", field_type, destructors), assignment]
        return [assignment]
    if kind == "binary":
        if result is None or len(operands) != 2 or instruction.symbol not in _BINARY:
            raise MirToCError("binary instruction requires a supported operator, two operands, and a result")
        operand_type = None
        if local_types is not None and instruction.operands:
            operand_type = local_types.get(instruction.operands[0])
            if len(instruction.operands) > 1 and local_types.get(instruction.operands[1]) != operand_type:
                raise MirToCError("binary operand types disagree")
        decimal = _decimal_type(operand_type) if operand_type is not None else None
        bounded = _bounded_type(operand_type) if operand_type is not None else None
        if decimal is not None and instruction.symbol in _CHECKED_HELPERS:
            identity, _, scale, policy = decimal
            if instruction.symbol == "+":
                expression = f"(__int128){operands[0]} + (__int128){operands[1]}"
            elif instruction.symbol == "-":
                expression = f"(__int128){operands[0]} - (__int128){operands[1]}"
            elif instruction.symbol == "*":
                expression = f"merit_round_decimal((__int128){operands[0]} * (__int128){operands[1]}, {10 ** scale}, {policy})"
            elif instruction.symbol == "/":
                expression = f"merit_round_decimal((__int128){operands[0]} * {10 ** scale}, (__int128){operands[1]}, {policy})"
            else:
                raise MirToCError("decimal remainder is outside the alpha.1 surface")
            return [f"{result} = merit_check_decimal_{identity}({expression});"]
        if bounded is not None and instruction.symbol in _CHECKED_HELPERS:
            identity, _, _, _, base_type = bounded
            helper = f"merit_checked_{_checked_operation_name(instruction.symbol)}_{base_type.name}"
            return [f"{result} = merit_check_bounded_{identity}({helper}({operands[0]}, {operands[1]}));"]
        if instruction.numeric_policy == "checked" and instruction.symbol in _CHECKED_HELPERS:
            if local_types is None or instruction.result not in local_types:
                raise MirToCError("checked binary instruction requires a resolved result type")
            result_type = local_types[instruction.result]
            if result_type.arguments or result_type.name not in _INTEGER_TYPES:
                raise MirToCError(f"checked binary instruction has unsupported result type: {result_type.name}")
            helper = f"merit_checked_{_checked_operation_name(instruction.symbol)}_{result_type.name}"
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
        if instruction.symbol == "system_allocator":
            if operands or result is None:
                raise MirToCError("system_allocator requires no arguments and one result")
            return [f"{result} = merit_system_allocator();"]
        if instruction.symbol == "portable_allocator":
            if operands or result is None:
                raise MirToCError("portable_allocator requires no arguments and one result")
            return [f"{result} = merit_portable_allocator();"]
        if instruction.symbol == "allocator_compatible":
            if len(operands) != 2 or result is None:
                raise MirToCError("allocator_compatible requires two allocators and one result")
            return [f"{result} = merit_allocator_compatible({operands[0]}, {operands[1]});"]
        if instruction.symbol == "buffer_new":
            if len(operands) != 2 or result is None:
                raise MirToCError("buffer_new requires allocator, capacity, and one result")
            return [f"{result} = merit_buffer_new({operands[0]}, {operands[1]});"]
        if instruction.symbol == "buffer_from_string":
            if len(operands) != 2 or result is None:
                raise MirToCError("buffer_from_string requires allocator, String, and one result")
            return [f"{result} = merit_buffer_from_string({operands[0]}, {operands[1]});"]
        if instruction.symbol == "buffer_push":
            if len(operands) != 2 or result is not None:
                raise MirToCError("buffer_push requires mutable Buffer, byte, and no result")
            ownership = local_ownership.get(instruction.operands[0], "value")
            argument = operands[0] if ownership == "mutable_borrow" else f"&{operands[0]}"
            return [f"merit_buffer_push({argument}, {operands[1]});"]
        if instruction.symbol == "buffer_len":
            if len(operands) != 1 or result is None:
                raise MirToCError("buffer_len requires one Buffer argument and one result")
            ownership = local_ownership.get(instruction.operands[0], "value")
            argument = operands[0] if ownership in {"borrowed", "mutable_borrow"} else f"&{operands[0]}"
            return [f"{result} = merit_buffer_len({argument});"]
        if instruction.symbol in {"buffer_get", "buffer_slice", "buffer_allocator"}:
            expected = {"buffer_get": 2, "buffer_slice": 3, "buffer_allocator": 1}[instruction.symbol]
            if len(operands) != expected or result is None:
                raise MirToCError(f"{instruction.symbol} has invalid operands/result")
            ownership = local_ownership.get(instruction.operands[0], "value")
            argument = operands[0] if ownership in {"borrowed", "mutable_borrow"} else f"&{operands[0]}"
            arguments = ", ".join((argument, *operands[1:]))
            return [f"{result} = merit_{instruction.symbol}({arguments});"]
        if instruction.symbol == "string_len":
            if len(operands) != 1 or result is None:
                raise MirToCError("string_len requires one String argument and one result")
            return [f"{result} = merit_string_len({operands[0]});"]
        if instruction.symbol == "string_byte":
            if len(operands) != 2 or result is None:
                raise MirToCError("string_byte requires String, index, and one result")
            return [f"{result} = merit_string_byte({operands[0]}, {operands[1]});"]
        if instruction.symbol == "slice_len":
            if len(operands) != 1 or result is None:
                raise MirToCError("slice_len requires one ByteSlice and one result")
            return [f"{result} = merit_slice_len({operands[0]});"]
        if instruction.symbol == "slice_get":
            if len(operands) != 2 or result is None:
                raise MirToCError("slice_get requires ByteSlice, index, and one result")
            return [f"{result} = merit_slice_get({operands[0]}, {operands[1]});"]
        vector_operation = _vector_call_operation(instruction.symbol)
        if vector_operation is not None:
            if local_types is None:
                raise MirToCError("vector calls require resolved local types")
            if vector_operation == "new":
                if len(operands) != 2 or result is None:
                    raise MirToCError("vec_new requires allocator, capacity, and one result")
                vector_type = local_types.get(instruction.result)
            else:
                if not operands:
                    raise MirToCError(f"vec_{vector_operation} requires a vector receiver")
                vector_type = local_types.get(instruction.operands[0])
            if vector_type is None or _vector_type(vector_type) is None:
                raise MirToCError(f"vec_{vector_operation} has no canonical vector type")
            helper = _vector_runtime_name(vector_type, vector_operation)
            if vector_operation == "new":
                return [f"{result} = {helper}({operands[0]}, {operands[1]});"]
            receiver_ownership = local_ownership.get(instruction.operands[0], "value")
            receiver = operands[0] if receiver_ownership in {"borrowed", "mutable_borrow"} else f"&{operands[0]}"
            arguments = ", ".join((receiver, *operands[1:]))
            unit_operations = {"push", "set", "replace", "drop", "transfer"}
            if vector_operation in unit_operations:
                if result is not None:
                    raise MirToCError(f"vec_{vector_operation} cannot produce a result")
                if vector_operation == "transfer":
                    if len(operands) != 2:
                        raise MirToCError("vec_transfer requires destination and source")
                    source_ownership = local_ownership.get(instruction.operands[1], "value")
                    source = operands[1] if source_ownership == "mutable_borrow" else f"&{operands[1]}"
                    arguments = f"{receiver}, {source}"
                return [f"{helper}({arguments});"]
            if result is None:
                raise MirToCError(f"vec_{vector_operation} requires a result")
            return [f"{result} = {helper}({arguments});"]
        callee = functions.get(instruction.symbol)
        if callee is None:
            raise MirToCError(f"call references unknown MIR function: {instruction.symbol}")
        if len(operands) != len(callee.parameters):
            raise MirToCError("MIR call argument count disagrees with callee parameters")
        arguments: list[str] = []
        for operand_id, operand, parameter in zip(instruction.operands, operands, callee.parameters):
            ownership = local_ownership.get(operand_id, "value")
            if parameter.mode == "value":
                if ownership in {"borrowed", "mutable_borrow"}:
                    raise MirToCError("borrowed MIR values cannot satisfy value parameters")
                arguments.append(operand)
            elif parameter.mode == "borrowed":
                arguments.append(operand if ownership in {"borrowed", "mutable_borrow"} else f"&{operand}")
            else:
                if ownership == "borrowed":
                    raise MirToCError("shared borrowed MIR values cannot satisfy mutable-borrow parameters")
                arguments.append(operand if ownership == "mutable_borrow" else f"&{operand}")
        callee_type = _type(callee.return_type)
        call = f"{_identifier(callee.name)}({', '.join(arguments)})"
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
        if local_types is not None and instruction.operands[0] in local_types:
            operand_type = local_types[instruction.operands[0]]
            decimal = _decimal_type(operand_type)
            if decimal is not None:
                return [f"merit_print_decimal((__int128){operands[0]}, {decimal[2]});"]
            bounded = _bounded_type(operand_type)
            if bounded is not None and bounded[4].name.startswith("u"):
                return [f'printf("%llu\\n", (unsigned long long){operands[0]});']
            if operand_type.name in {"String", "Buffer"} and not operand_type.arguments:
                access = "."
                if operand_type.name == "Buffer" and local_ownership.get(instruction.operands[0]) in {
                    "borrowed",
                    "mutable_borrow",
                }:
                    access = "->"
                return [
                    f"fwrite({operands[0]}{access}data, 1, {operands[0]}{access}len, stdout);",
                    "putchar('\\n');",
                ]
        return [f'printf("%lld\\n", (long long){operands[0]});']
    if kind == "drop":
        if len(operands) != 1:
            raise MirToCError("drop instruction requires one operand")
        if local_types is not None and instruction.operands[0] in local_types:
            operand_type = local_types[instruction.operands[0]]
            if _vector_type(operand_type) is not None:
                return _drop_statements(operands[0], operand_type, destructors)
            if operand_type.name == "Buffer" and not operand_type.arguments:
                return _drop_statements(operands[0], operand_type, destructors)
            if _aggregate_struct_identity(operand_type) is not None:
                return _drop_statements(operands[0], operand_type, destructors)
            if _destructor_i64_struct_identity(operand_type) is not None:
                if operand_type in destructors:
                    return [f"{_destructor_c_name(operand_type)}(&{operands[0]});"]
                return [f'printf("%lld\\n", (long long){operands[0]}.field_0);']
            if _owned_payload_enum_identity(operand_type) is not None:
                return [f'printf("%lld\\n", (long long){operands[0]}.payload.field_0);']
            recursive_enum = _recursive_owned_payload_enum_identity(operand_type)
            if recursive_enum is not None:
                return _drop_statements(operands[0], operand_type, destructors)
            owned_struct = _owned_field_struct_identity(operand_type)
            if owned_struct is not None:
                return _drop_statements(f"{operands[0]}.field_0", owned_struct[1], destructors)
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
    return f"{_function_return_type(function)} {_identifier(function.name)}({_parameter_list(function)});"


def _function_return_type(function: MirFunction) -> str:
    base = _type(function.return_type)
    if function.return_mode == "borrowed":
        return f"const {base} *"
    if function.return_mode == "mutable_borrow":
        return f"{base} *"
    return base


def _parameter_list(function: MirFunction) -> str:
    if not function.parameters:
        return "void"
    locals_by_id = {local.local_id: local for local in function.locals}
    rendered: list[str] = []
    for parameter in function.parameters:
        local = locals_by_id[parameter.local_id]
        type_name = _type(local.type)
        if parameter.mode == "borrowed":
            type_name = f"const {type_name} *"
        elif parameter.mode == "mutable_borrow":
            type_name = f"{type_name} *"
        rendered.append(f"{type_name} {_local(parameter.local_id)}")
    return ", ".join(rendered)


def _local_initializer(type_: MirType) -> str:
    if (
        type_.name in {"Allocator", "Buffer", "String", "ByteSlice"}
        or _copy_payload_enum_identity(type_) is not None
        or _i64_struct_identity(type_) is not None
        or _destructor_i64_struct_identity(type_) is not None
        or _owned_payload_enum_identity(type_) is not None
        or _owned_field_struct_identity(type_) is not None
        or _recursive_owned_payload_enum_identity(type_) is not None
        or _aggregate_struct_identity(type_) is not None
        or _vector_type(type_) is not None
    ):
        return "{0}"
    return "0"


def emit_c_function(
    function: MirFunction,
    functions: dict[str, MirFunction] | None = None,
    destructors: dict[MirType, MirDestructor] | None = None,
) -> str:
    functions = functions or {function.name: function}
    destructors = destructors or {}
    return_type = _function_return_type(function)
    lines = [f"{return_type} {_identifier(function.name)}({_parameter_list(function)}) {{"]
    local_types = {local.local_id: local.type for local in function.locals}
    local_ownership = {local.local_id: local.ownership for local in function.locals}
    parameter_ids = {parameter.local_id for parameter in function.parameters}
    for local in function.locals:
        if local.local_id in parameter_ids:
            continue
        local_type = _type(local.type)
        if local_type == "void":
            raise MirToCError("MIR locals cannot have unit type in core C emission")
        initializer = _local_initializer(local.type)
        if local.ownership == "borrowed":
            lines.append(f"    const {local_type} *{_local(local.local_id)} = NULL;")
        elif local.ownership == "mutable_borrow":
            lines.append(f"    {local_type} *{_local(local.local_id)} = NULL;")
        else:
            lines.append(f"    {local_type} {_local(local.local_id)} = {initializer};")
    lines.append(f"    goto b{function.entry_block};")
    for block in function.blocks:
        lines.append(f"b{block.block_id}:")
        for instruction in block.instructions:
            for statement in _instruction(instruction, functions, local_types, local_ownership, destructors):
                lines.append(f"    {statement}")
        for statement in _terminator(block.terminator, return_type):
            lines.append(f"    {statement}")
    lines.append("}")
    return "\n".join(lines)


def _emit_c_destructor(
    destructor: MirDestructor,
    functions: dict[str, MirFunction],
    destructors: dict[MirType, MirDestructor],
) -> str:
    local_types = {local.local_id: local.type for local in destructor.locals}
    lines = [
        f"static void {_destructor_c_name(destructor.target)}({_type(destructor.target)} *self) {{",
        f"    {_type(destructor.target)} {_local(0)} = *self;",
    ]
    for local in destructor.locals[1:]:
        lines.append(
            f"    {_type(local.type)} {_local(local.local_id)} = "
            f"{_local_initializer(local.type)};"
        )
    lines.append(f"    goto b_destructor_{destructor.entry_block};")
    for block in destructor.blocks:
        lines.append(f"b_destructor_{block.block_id}:")
        for instruction in block.instructions:
            for statement in _instruction(instruction, functions, local_types, {}, destructors):
                lines.append(f"    {statement}")
        if block.terminator.kind == "return":
            if block.terminator.operands:
                raise MirToCError("destructor return terminators cannot carry values")
            lines.extend(["    *self = m0;", "    return;"])
        else:
            for statement in _terminator(block.terminator, "void"):
                lines.append(f"    {statement.replace('goto b', 'goto b_destructor_')}")
    lines.append("}")
    return "\n".join(lines)


def _checked_operation_name(symbol: str) -> str:
    return {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}[symbol]


def _checked_helpers(operations: set[tuple[str, str]]) -> list[str]:
    if not operations:
        return []
    lines = [
        'static void merit_numeric_failure(const char *operation) { fprintf(stderr, "Merit %s\\n", operation); exit(70); }',
    ]
    if any(symbol in {"/", "%"} for _, symbol in operations):
        lines.append('static void merit_division_by_zero(void) { fprintf(stderr, "Merit division by zero\\n"); exit(72); }')
    for type_name, symbol in sorted(operations):
        c_type = _C_TYPES[type_name]
        operation = _checked_operation_name(symbol)
        signed = type_name.startswith("i")
        bits = int(type_name[1:])
        minimum = f"INT{bits}_MIN"
        maximum = f"INT{bits}_MAX" if signed else f"UINT{bits}_MAX"
        helper = f"merit_checked_{operation}_{type_name}"
        lines.append(f"static {c_type} {helper}({c_type} a, {c_type} b) {{")
        if symbol == "+":
            wide = "__int128" if signed else "unsigned __int128"
            lines.append(f"    {wide} result = ({wide})a + ({wide})b;")
            condition = f"result < {minimum} || result > {maximum}" if signed else f"result > {maximum}"
            lines.append(f"    if ({condition}) merit_numeric_failure(\"{type_name} addition overflow\");")
            lines.append(f"    return ({c_type})result;")
        elif symbol == "-":
            if signed:
                lines.append("    __int128 result = (__int128)a - (__int128)b;")
                lines.append(f"    if (result < {minimum} || result > {maximum}) merit_numeric_failure(\"{type_name} subtraction overflow\");")
                lines.append(f"    return ({c_type})result;")
            else:
                lines.append(f"    if (a < b) merit_numeric_failure(\"{type_name} subtraction overflow\");")
                lines.append(f"    return ({c_type})(a - b);")
        elif symbol == "*":
            wide = "__int128" if signed else "unsigned __int128"
            lines.append(f"    {wide} result = ({wide})a * ({wide})b;")
            condition = f"result < {minimum} || result > {maximum}" if signed else f"result > {maximum}"
            lines.append(f"    if ({condition}) merit_numeric_failure(\"{type_name} multiplication overflow\");")
            lines.append(f"    return ({c_type})result;")
        else:
            lines.append("    if (b == 0) merit_division_by_zero();")
            if signed:
                lines.append(f"    if (a == {minimum} && b == -1) merit_numeric_failure(\"division overflow\");")
            lines.append(f"    return ({c_type})(a {symbol} b);")
        lines.append("}")
    return lines


def _exact_numeric_helpers(types: set[MirType]) -> list[str]:
    decimal_types = sorted(
        ((type_, _decimal_type(type_)) for type_ in types if _decimal_type(type_) is not None),
        key=lambda item: item[1][0],
    )
    bounded_types = sorted(
        ((type_, _bounded_type(type_)) for type_ in types if _bounded_type(type_) is not None),
        key=lambda item: item[1][0],
    )
    if not decimal_types and not bounded_types:
        return []
    lines = [
        'static void merit_exact_numeric_failure(const char *message) { fprintf(stderr, "Merit %s\\n", message); exit(70); }',
    ]
    if decimal_types:
        lines.extend([
            "static __int128 merit_round_decimal(__int128 numerator, __int128 denominator, int mode) {",
            '    if (denominator == 0) { fprintf(stderr, "Merit division by zero\\n"); exit(72); }',
            "    int negative = (numerator < 0) ^ (denominator < 0);",
            "    if (numerator < 0) numerator = -numerator; if (denominator < 0) denominator = -denominator;",
            "    __int128 quotient = numerator / denominator; __int128 remainder = numerator % denominator; int round_up = 0;",
            "    if (mode == 0) { __int128 twice = remainder * 2; round_up = twice > denominator || (twice == denominator && (quotient & 1)); }",
            "    else if (mode == 1) round_up = remainder * 2 >= denominator;",
            "    else if (mode == 3) round_up = !negative && remainder != 0;",
            "    else if (mode == 4) round_up = negative && remainder != 0;",
            "    quotient += round_up; return negative ? -quotient : quotient;",
            "}",
        ])
    for type_, descriptor in decimal_types:
        identity, precision, _, _ = descriptor
        maximum = 10 ** precision - 1
        limit = f"(__int128)INT64_C({maximum})" if precision <= 18 else _int128_literal(maximum)
        lines.extend([
            f"static {_type(type_)} merit_check_decimal_{identity}(__int128 value) {{",
            f'    if (value < -({limit}) || value > ({limit})) merit_exact_numeric_failure("decimal range violation");',
            f"    return ({_type(type_)})value;",
            "}",
        ])
    for type_, descriptor in bounded_types:
        identity, _, minimum, maximum, _ = descriptor
        lines.extend([
            f"static {_type(type_)} merit_check_bounded_{identity}(__int128 value) {{",
            f'    if (value < {_int128_literal(minimum)} || value > {_int128_literal(maximum)}) merit_exact_numeric_failure("bounded range violation");',
            f"    return ({_type(type_)})value;",
            "}",
        ])
    return lines


def _walk_types(type_: MirType) -> tuple[MirType, ...]:
    result = [type_]
    for argument in type_.arguments:
        result.extend(_walk_types(argument))
    return tuple(result)


def _type_needs_print(type_: MirType) -> bool:
    aggregate = _aggregate_struct_identity(type_)
    return (
        _destructor_i64_struct_identity(type_) is not None
        or _owned_payload_enum_identity(type_) is not None
        or (aggregate is not None and aggregate[2] is not None)
        or any(_type_needs_print(argument) for argument in type_.arguments)
    )


def emit_c_module(module: MirModule) -> str:
    functions = _function_table(module)
    destructors = {destructor.target: destructor for destructor in module.destructors}
    instructions = [
        instruction
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    ] + [
        instruction
        for destructor in module.destructors
        for block in destructor.blocks
        for instruction in block.instructions
    ]
    needs_contract = any(instruction.kind == "contract_check" for instruction in instructions)
    needs_capability = any(instruction.kind == "capability_check" for instruction in instructions)
    needs_print = any(instruction.kind == "print" for instruction in instructions) or any(
        _type_needs_print(local.type) for function in module.functions for local in function.locals
    )
    all_types = {
        nested
        for function in module.functions
        for local in function.locals
        for nested in _walk_types(local.type)
    } | {
        nested
        for destructor in module.destructors
        for type_ in (destructor.target, *(local.type for local in destructor.locals))
        for nested in _walk_types(type_)
    }
    vector_types = tuple(sorted(
        (type_ for type_ in all_types if _vector_type(type_) is not None),
        key=_type_mangle,
    ))
    checked_operations: set[tuple[str, str]] = set()
    for executable in (*module.functions, *module.destructors):
        executable_types = {local.local_id: local.type for local in executable.locals}
        for block in executable.blocks:
            for instruction in block.instructions:
                if (
                    instruction.kind == "binary"
                    and instruction.numeric_policy == "checked"
                    and instruction.symbol in _CHECKED_HELPERS
                    and instruction.result is not None
                    and executable_types[instruction.result].name in _INTEGER_TYPES
                ):
                    checked_operations.add(
                        (executable_types[instruction.result].name, instruction.symbol)
                    )
                if (
                    instruction.kind == "binary"
                    and instruction.symbol in _CHECKED_HELPERS
                    and instruction.operands
                    and (bounded := _bounded_type(executable_types[instruction.operands[0]])) is not None
                ):
                    checked_operations.add((bounded[4].name, instruction.symbol))
    needs_buffer_runtime = bool(vector_types) or any(
        type_.name in {"Allocator", "Buffer"} and not type_.arguments
        for type_ in all_types
    )
    needs_text_runtime=any(type_.name in {"String","ByteSlice"} and not type_.arguments for type_ in all_types)
    needs_decimal_runtime = any(_decimal_type(type_) is not None for type_ in all_types)
    prelude = [
        "/* generated from bootstrap-mir-v1; deterministic, do not edit */",
        "#include <stdbool.h>",
        *(["#include <stddef.h>"] if needs_buffer_runtime or needs_text_runtime else []),
        "#include <stdint.h>",
        *(["#include <stdio.h>"] if needs_print or checked_operations or needs_decimal_runtime or needs_buffer_runtime or needs_text_runtime else []),
        "#include <stdlib.h>",
        *(["#include <string.h>"] if needs_buffer_runtime else []),
        "",
        *([
            "typedef struct { const uint8_t *data; size_t len; } merit_String;",
            "typedef struct { const uint8_t *data; size_t len; } merit_ByteSlice;",
            "static inline int64_t merit_string_len(merit_String value) { return (int64_t)value.len; }",
            "static inline uint8_t merit_string_byte(merit_String value, int64_t index) {",
            "    if (index < 0 || (size_t)index >= value.len) return 0;",
            "    return value.data[index];",
            "}",
            "",
        ] if needs_text_runtime or needs_buffer_runtime else []),
        *([
            "typedef struct { int32_t identity; } merit_Allocator;",
            "typedef struct { uint8_t *data; size_t len; size_t capacity; merit_Allocator allocator; } merit_Buffer;",
            "static inline merit_Allocator merit_system_allocator(void) { return (merit_Allocator){0}; }",
            "static inline merit_Allocator merit_portable_allocator(void) { return (merit_Allocator){1}; }",
            "static inline int32_t merit_allocator_compatible(merit_Allocator left, merit_Allocator right) { return left.identity == right.identity; }",
            "static inline void merit_buffer_reserve(merit_Buffer *value, size_t needed) {",
            "    if (needed <= value->capacity) return;",
            "    size_t capacity = value->capacity ? value->capacity : 8;",
            "    while (capacity < needed) capacity *= 2;",
            "    void *data = realloc(value->data, capacity);",
            '    if (!data) { fprintf(stderr, "Merit allocation failed\\n"); exit(80); }',
            "    value->data = (uint8_t *)data; value->capacity = capacity;",
            "}",
            "static inline merit_Buffer merit_buffer_new(merit_Allocator allocator, int64_t capacity) {",
            '    if (capacity < 0) { fprintf(stderr, "Merit negative capacity\\n"); exit(81); }',
            "    merit_Buffer result = {0}; result.allocator = allocator; merit_buffer_reserve(&result, (size_t)capacity);",
            "    return result;",
            "}",
            "static inline merit_Buffer merit_buffer_from_string(merit_Allocator allocator, merit_String value) {",
            "    merit_Buffer result = merit_buffer_new(allocator, (int64_t)value.len);",
            "    if (value.len) { memcpy(result.data, value.data, value.len); result.len = value.len; } return result;",
            "}",
            "static inline void merit_buffer_push(merit_Buffer *value, uint8_t byte) { merit_buffer_reserve(value, value->len + 1); value->data[value->len++] = byte; }",
            "static inline int64_t merit_buffer_len(const merit_Buffer *value) { return (int64_t)value->len; }",
            "static inline int64_t merit_buffer_get(const merit_Buffer *value, int64_t index) {",
            '    if (index < 0 || (size_t)index >= value->len) { fprintf(stderr, "Merit buffer index out of bounds\\n"); exit(82); }',
            "    return (int64_t)value->data[index];",
            "}",
            "static inline merit_ByteSlice merit_buffer_slice(const merit_Buffer *value, int64_t start, int64_t length) {",
            '    if (start < 0 || length < 0 || (size_t)start > value->len || (size_t)length > value->len - (size_t)start) { fprintf(stderr, "Merit slice out of bounds\\n"); exit(85); }',
            "    return (merit_ByteSlice){value->data + (size_t)start, (size_t)length};",
            "}",
            "static inline merit_Allocator merit_buffer_allocator(const merit_Buffer *value) { return value->allocator; }",
            "static inline int64_t merit_slice_len(merit_ByteSlice value) { return (int64_t)value.len; }",
            "static inline int64_t merit_slice_get(merit_ByteSlice value, int64_t index) {",
            '    if (index < 0 || (size_t)index >= value.len) { fprintf(stderr, "Merit slice index out of bounds\\n"); exit(85); }',
            "    return (int64_t)value.data[index];",
            "}",
            "static inline void merit_buffer_drop(merit_Buffer *value) { free(value->data); value->data = NULL; value->len = 0; value->capacity = 0; }",
            "",
        ] if needs_buffer_runtime else []),
        *([
            "static void merit_print_u128(unsigned __int128 value) {",
            "    char digits[40]; int count = 0;",
            "    do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value != 0);",
            "    while (count > 0) putchar(digits[--count]);",
            "}",
            "static void merit_print_decimal(__int128 value, int scale) {",
            "    unsigned __int128 magnitude;",
            "    if (value < 0) { putchar('-'); magnitude = (unsigned __int128)(-(value + 1)) + 1; }",
            "    else { magnitude = (unsigned __int128)value; }",
            "    unsigned __int128 factor = 1; for (int i = 0; i < scale; ++i) factor *= 10;",
            "    merit_print_u128(magnitude / factor);",
            "    if (scale > 0) {",
            "        putchar('.'); unsigned __int128 fraction = magnitude % factor;",
            "        unsigned __int128 place = factor / 10;",
            "        while (place > 0) { putchar((int)('0' + (fraction / place) % 10)); place /= 10; }",
            "    }",
            "    putchar('\\n');",
            "}",
            "",
        ] if needs_decimal_runtime else []),
    ]
    if vector_types:
        prelude.extend([
            *[
                f"typedef struct {{ void *data; size_t len; size_t capacity; merit_Allocator allocator; }} {_type(type_)};"
                for type_ in vector_types
            ],
            "",
        ])
    enum_identities = sorted({
        identity
        for type_ in all_types
        if (identity := _copy_payload_enum_identity(type_)) is not None
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
        for type_ in all_types
        if (identity := _i64_struct_identity(type_)) is not None
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
        for type_ in all_types
        if (identity := _destructor_i64_struct_identity(type_)) is not None
    }, key=int)
    if destructor_struct_identities:
        prelude.extend([
            *[
                f"typedef struct {{ int64_t field_0; }} merit_struct_i64_destructor_{identity};"
                for identity in destructor_struct_identities
            ],
            "",
        ])
    owned_field_structs = {
        identity: child
        for type_ in all_types
        if (owned := _owned_field_struct_identity(type_)) is not None
        for identity, child in (owned,)
    }
    if owned_field_structs:
        pending = dict(owned_field_structs)
        emitted_owned: set[str] = set()
        definitions: list[str] = []
        while pending:
            progressed = False
            for identity, child in sorted(pending.items(), key=lambda item: int(item[0])):
                dependency = _owned_field_struct_identity(child)
                if dependency is not None and dependency[0] not in emitted_owned:
                    continue
                definitions.append(
                    f"typedef struct {{ {_type(child)} field_0; }} merit_struct_owned_field_{identity};"
                )
                emitted_owned.add(identity)
                del pending[identity]
                progressed = True
                break
            if not progressed:
                raise MirToCError("owned-field struct type graph is cyclic")
        prelude.extend([*definitions, ""])
    aggregate_structs = {
        identity: (fields, destructor_field)
        for type_ in all_types
        if (aggregate := _aggregate_struct_identity(type_)) is not None
        for identity, fields, destructor_field in (aggregate,)
    }
    if aggregate_structs:
        pending = dict(aggregate_structs)
        emitted_aggregates: set[str] = set()
        definitions: list[str] = []
        while pending:
            progressed = False
            for identity, (fields, _) in sorted(pending.items(), key=lambda item: int(item[0])):
                dependencies = {
                    dependency[0]
                    for field in fields
                    if (dependency := _aggregate_struct_identity(field)) is not None
                }
                if not dependencies <= emitted_aggregates:
                    continue
                members = " ".join(
                    f"{_type(field)} field_{ordinal};"
                    for ordinal, field in enumerate(fields)
                )
                definitions.append(f"typedef struct {{ {members} }} merit_struct_aggregate_{identity};")
                emitted_aggregates.add(identity)
                del pending[identity]
                progressed = True
                break
            if not progressed:
                raise MirToCError("aggregate struct type graph is cyclic")
        prelude.extend([*definitions, ""])
    owned_enum_identities = sorted({
        identity
        for type_ in all_types
        if (identity := _owned_payload_enum_identity(type_)) is not None
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
    recursive_owned_enums = {
        identity: payloads
        for type_ in all_types
        if (owned := _recursive_owned_payload_enum_identity(type_)) is not None
        for identity, payloads in (owned,)
    }
    if recursive_owned_enums:
        prelude.extend([
            *[
                "typedef struct { int64_t tag; union { "
                + " ".join(
                    f"{_type(payload)} variant_{ordinal};"
                    for ordinal, payload in enumerate(payloads)
                )
                + f" }} payload; }} merit_enum_owned_payload_{identity};"
                for identity, payloads in sorted(recursive_owned_enums.items(), key=lambda item: int(item[0]))
            ],
            "",
        ])
    prototypes = [_prototype(function) for function in module.functions]
    prototypes.extend(
        f"static void {_destructor_c_name(destructor.target)}({_type(destructor.target)} *self);"
        for destructor in module.destructors
    )
    if prototypes:
        prelude.extend([*prototypes, ""])
    runtime = [
        *_checked_helpers(checked_operations),
        *_exact_numeric_helpers(all_types),
        *_vector_runtime(vector_types, destructors),
    ]
    if needs_contract:
        runtime.append("static void merit_contract_failure(const char *kind) { (void)kind; abort(); }")
    if needs_capability:
        runtime.append("static void merit_capability_check(const char *capability) { (void)capability; }")
    if runtime:
        prelude.extend([*runtime, ""])
    emitted_destructors = [
        _emit_c_destructor(destructor, functions, destructors)
        for destructor in module.destructors
    ]
    emitted_functions = [
        emit_c_function(function, functions, destructors)
        for function in module.functions
    ]
    emitted = "\n\n".join([*emitted_destructors, *emitted_functions])
    return "\n".join([*prelude, emitted, ""])
