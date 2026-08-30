"""Versioned, backend-neutral MIR contract for Merit bootstrap comparison.

MIR is the ordered operational boundary after semantic checking and before C
emission. It makes control flow, temporaries, ownership transfers, drops,
contracts, capabilities, and numeric behavior explicit so the backend cannot
accidentally define Merit semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Sequence

MIR_SCHEMA = "bootstrap-mir-v1"

INSTRUCTION_KINDS = frozenset({
    "const", "copy", "move", "borrow", "load_field", "store_field",
    "binary", "convert", "call", "construct", "contract_check",
    "capability_check", "allocate", "deallocate", "drop", "nop",
    "print",
})
TERMINATOR_KINDS = frozenset({"return", "jump", "branch", "switch", "unreachable"})
OWNERSHIP_MODES = frozenset({"value", "owned", "borrowed", "mutable_borrow", "moved", "none"})
NUMERIC_POLICIES = frozenset({"exact", "checked", "wrapping", "saturating", "floating", "none"})
CONVERSION_POLICIES = frozenset({"exact", "checked", "round", "truncate", "reinterpret", "none"})
CONTRACT_KINDS = frozenset({"precondition", "postcondition", "invariant", "none"})


class MirContractError(ValueError):
    """Raised when MIR violates ``bootstrap-mir-v1``."""


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: int
    length: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.length < 0:
            raise MirContractError("source spans must be non-negative")

    def to_data(self) -> list[int]:
        return [self.start, self.length]


@dataclass(frozen=True, slots=True)
class MirType:
    name: str
    arguments: tuple["MirType", ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise MirContractError("MIR type name must be non-empty")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {"name": self.name}
        if self.arguments:
            data["arguments"] = [argument.to_data() for argument in self.arguments]
        return data


@dataclass(frozen=True, slots=True)
class MirLocal:
    local_id: int
    name: str
    type: MirType
    mutable: bool = False
    ownership: str = "value"
    source_binding_id: int | None = None

    def __post_init__(self) -> None:
        if self.local_id < 0:
            raise MirContractError("local IDs must be non-negative")
        if not self.name:
            raise MirContractError("local names must be non-empty")
        if self.ownership not in OWNERSHIP_MODES:
            raise MirContractError(f"unknown ownership mode: {self.ownership}")
        if self.source_binding_id is not None and self.source_binding_id < 0:
            raise MirContractError("source binding IDs must be non-negative")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "id": self.local_id,
            "name": self.name,
            "type": self.type.to_data(),
            "mutable": self.mutable,
            "ownership": self.ownership,
        }
        if self.source_binding_id is not None:
            data["source_binding_id"] = self.source_binding_id
        return data


@dataclass(frozen=True, slots=True)
class MirParameter:
    local_id: int
    mode: str = "value"

    def __post_init__(self) -> None:
        if self.local_id < 0:
            raise MirContractError("parameter local IDs must be non-negative")
        if self.mode not in {"value", "borrowed", "mutable_borrow"}:
            raise MirContractError(f"unknown parameter mode: {self.mode}")

    def to_data(self) -> dict[str, object]:
        return {"local": self.local_id, "mode": self.mode}


@dataclass(frozen=True, slots=True)
class MirInstruction:
    instruction_id: int
    kind: str
    result: int | None = None
    operands: tuple[int, ...] = ()
    symbol: str | None = None
    value: object | None = None
    span: SourceSpan | None = None
    ownership: str = "none"
    numeric_policy: str = "none"
    conversion_policy: str = "none"
    contract_kind: str = "none"
    capabilities: tuple[str, ...] = ()
    specialization: tuple[MirType, ...] = ()

    def __post_init__(self) -> None:
        if self.instruction_id < 0:
            raise MirContractError("instruction IDs must be non-negative")
        if self.kind not in INSTRUCTION_KINDS:
            raise MirContractError(f"unknown MIR instruction kind: {self.kind}")
        if self.result is not None and self.result < 0:
            raise MirContractError("result local IDs must be non-negative")
        if any(operand < 0 for operand in self.operands):
            raise MirContractError("operand local IDs must be non-negative")
        if self.ownership not in OWNERSHIP_MODES:
            raise MirContractError(f"unknown ownership mode: {self.ownership}")
        if self.numeric_policy not in NUMERIC_POLICIES:
            raise MirContractError(f"unknown numeric policy: {self.numeric_policy}")
        if self.conversion_policy not in CONVERSION_POLICIES:
            raise MirContractError(f"unknown conversion policy: {self.conversion_policy}")
        if self.contract_kind not in CONTRACT_KINDS:
            raise MirContractError(f"unknown contract kind: {self.contract_kind}")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise MirContractError("capability requirements must be unique")
        if any(not capability for capability in self.capabilities):
            raise MirContractError("capability names must be non-empty")
        if self.specialization and self.kind != "call":
            raise MirContractError("generic specialization is only valid on call instructions")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "id": self.instruction_id,
            "kind": self.kind,
            "operands": list(self.operands),
            "ownership": self.ownership,
            "numeric_policy": self.numeric_policy,
            "conversion_policy": self.conversion_policy,
            "contract_kind": self.contract_kind,
        }
        if self.result is not None:
            data["result"] = self.result
        if self.symbol is not None:
            data["symbol"] = self.symbol
        if self.value is not None:
            data["value"] = self.value
        if self.span is not None:
            data["span"] = self.span.to_data()
        if self.capabilities:
            data["capabilities"] = list(self.capabilities)
        if self.specialization:
            data["specialization"] = [argument.to_data() for argument in self.specialization]
        return data


@dataclass(frozen=True, slots=True)
class MirTerminator:
    kind: str
    operands: tuple[int, ...] = ()
    targets: tuple[int, ...] = ()
    cases: tuple[int, ...] = ()
    span: SourceSpan | None = None

    def __post_init__(self) -> None:
        if self.kind not in TERMINATOR_KINDS:
            raise MirContractError(f"unknown MIR terminator kind: {self.kind}")
        if any(value < 0 for value in self.operands + self.targets):
            raise MirContractError("terminator references must be non-negative")
        if self.kind == "return" and len(self.targets) != 0:
            raise MirContractError("return terminators cannot have targets")
        if self.kind == "jump" and len(self.targets) != 1:
            raise MirContractError("jump terminators require exactly one target")
        if self.kind == "branch" and (len(self.operands) != 1 or len(self.targets) != 2):
            raise MirContractError("branch terminators require one condition and two targets")
        if self.kind == "switch":
            if len(self.operands) != 1 or len(self.targets) != len(self.cases) + 1:
                raise MirContractError("switch requires one operand, case targets, and a default target")
        if self.kind == "unreachable" and (self.operands or self.targets or self.cases):
            raise MirContractError("unreachable terminators cannot carry references")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "kind": self.kind,
            "operands": list(self.operands),
            "targets": list(self.targets),
        }
        if self.cases:
            data["cases"] = list(self.cases)
        if self.span is not None:
            data["span"] = self.span.to_data()
        return data


@dataclass(frozen=True, slots=True)
class MirBlock:
    block_id: int
    instructions: tuple[MirInstruction, ...]
    terminator: MirTerminator

    def __post_init__(self) -> None:
        if self.block_id < 0:
            raise MirContractError("block IDs must be non-negative")

    def to_data(self) -> dict[str, object]:
        return {
            "id": self.block_id,
            "instructions": [instruction.to_data() for instruction in self.instructions],
            "terminator": self.terminator.to_data(),
        }


@dataclass(frozen=True, slots=True)
class MirFunction:
    name: str
    return_type: MirType
    locals: tuple[MirLocal, ...]
    blocks: tuple[MirBlock, ...]
    entry_block: int
    capabilities: tuple[str, ...] = ()
    parameters: tuple[MirParameter, ...] = ()
    return_mode: str = "value"
    borrowed_origin: int | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise MirContractError("function names must be non-empty")
        if self.entry_block < 0:
            raise MirContractError("entry block IDs must be non-negative")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise MirContractError("function capability requirements must be unique")
        if any(not capability for capability in self.capabilities):
            raise MirContractError("function capability names must be non-empty")
        if self.return_mode not in {"value", "borrowed", "mutable_borrow"}:
            raise MirContractError(f"unknown function return mode: {self.return_mode}")
        parameter_ids = [parameter.local_id for parameter in self.parameters]
        if len(set(parameter_ids)) != len(parameter_ids):
            raise MirContractError("function parameter locals must be unique")
        locals_by_id = {local.local_id: local for local in self.locals}
        for parameter in self.parameters:
            local = locals_by_id.get(parameter.local_id)
            if local is None:
                raise MirContractError("function parameters must reference declared locals")
            if parameter.mode != "value" and local.ownership != parameter.mode:
                raise MirContractError("borrowed parameter mode must match local ownership")
        if self.return_mode == "value":
            if self.borrowed_origin is not None:
                raise MirContractError("value returns cannot declare a borrowed origin")
        else:
            if self.borrowed_origin not in parameter_ids:
                raise MirContractError("borrowed returns require a parameter origin")
            origin = next(parameter for parameter in self.parameters if parameter.local_id == self.borrowed_origin)
            if origin.mode == "value":
                raise MirContractError("borrowed returns require a borrowed parameter origin")
            if self.return_mode == "mutable_borrow" and origin.mode != "mutable_borrow":
                raise MirContractError("mutable borrowed returns require a mutable-borrow origin")
        _validate_function(self)

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "return_type": self.return_type.to_data(),
            "locals": [local.to_data() for local in self.locals],
            "blocks": [block.to_data() for block in self.blocks],
            "entry_block": self.entry_block,
            "capabilities": list(self.capabilities),
        }
        if self.parameters:
            data["parameters"] = [parameter.to_data() for parameter in self.parameters]
        if self.return_mode != "value":
            data["return_mode"] = self.return_mode
            data["borrowed_origin"] = self.borrowed_origin
        return data


@dataclass(frozen=True, slots=True)
class MirDestructor:
    target: MirType
    locals: tuple[MirLocal, ...]
    blocks: tuple[MirBlock, ...]
    entry_block: int

    def __post_init__(self) -> None:
        if self.entry_block < 0:
            raise MirContractError("destructor entry block IDs must be non-negative")
        if not self.locals or self.locals[0].name != "self":
            raise MirContractError("destructors require self as local 0")
        if self.locals[0].local_id != 0 or self.locals[0].type != self.target:
            raise MirContractError("destructor self local must have its target type")
        if self.locals[0].ownership != "mutable_borrow":
            raise MirContractError("destructor self local must be a mutable borrow")
        _validate_executable(self.locals, self.blocks, self.entry_block)

    def to_data(self) -> dict[str, object]:
        return {
            "target": self.target.to_data(),
            "locals": [local.to_data() for local in self.locals],
            "blocks": [block.to_data() for block in self.blocks],
            "entry_block": self.entry_block,
        }


@dataclass(frozen=True, slots=True)
class MirModule:
    name: str
    functions: tuple[MirFunction, ...]
    schema: str = MIR_SCHEMA
    destructors: tuple[MirDestructor, ...] = ()

    def __post_init__(self) -> None:
        if self.schema != MIR_SCHEMA:
            raise MirContractError(f"expected MIR schema {MIR_SCHEMA!r}")
        if not self.name:
            raise MirContractError("module name must be non-empty")
        names = [function.name for function in self.functions]
        if len(set(names)) != len(names):
            raise MirContractError("duplicate MIR function name")
        targets = [destructor.target for destructor in self.destructors]
        if len(set(targets)) != len(targets):
            raise MirContractError("duplicate MIR destructor target")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema": self.schema,
            "name": self.name,
            "functions": [function.to_data() for function in self.functions],
        }
        if self.destructors:
            data["destructors"] = [destructor.to_data() for destructor in self.destructors]
        return data


def _validate_function(function: MirFunction) -> None:
    _validate_executable(function.locals, function.blocks, function.entry_block)


def _validate_executable(
    locals_: tuple[MirLocal, ...], blocks: tuple[MirBlock, ...], entry_block: int
) -> None:
    local_ids = [local.local_id for local in locals_]
    block_ids = [block.block_id for block in blocks]
    instruction_ids = [instruction.instruction_id for block in blocks for instruction in block.instructions]
    if len(set(local_ids)) != len(local_ids):
        raise MirContractError("duplicate MIR local ID")
    if len(set(block_ids)) != len(block_ids):
        raise MirContractError("duplicate MIR block ID")
    if len(set(instruction_ids)) != len(instruction_ids):
        raise MirContractError("duplicate MIR instruction ID")
    local_set = set(local_ids)
    block_set = set(block_ids)
    if entry_block not in block_set:
        raise MirContractError("entry block does not exist")
    for block in blocks:
        previous = -1
        for instruction in block.instructions:
            if instruction.instruction_id <= previous:
                raise MirContractError("instructions within a block must be strictly ordered")
            previous = instruction.instruction_id
            if instruction.result is not None and instruction.result not in local_set:
                raise MirContractError(f"instruction {instruction.instruction_id} writes unknown local {instruction.result}")
            for operand in instruction.operands:
                if operand not in local_set:
                    raise MirContractError(f"instruction {instruction.instruction_id} reads unknown local {operand}")
            if instruction.kind == "binary" and instruction.numeric_policy == "none":
                raise MirContractError("binary instructions require an explicit numeric policy")
            if instruction.kind == "convert" and instruction.conversion_policy == "none":
                raise MirContractError("convert instructions require an explicit conversion policy")
            if instruction.kind == "contract_check" and instruction.contract_kind == "none":
                raise MirContractError("contract checks require an explicit contract kind")
            if instruction.kind == "capability_check" and not instruction.capabilities:
                raise MirContractError("capability checks require at least one capability")
            if instruction.kind in {"move", "borrow", "drop", "deallocate"} and not instruction.operands:
                raise MirContractError(f"{instruction.kind} instructions require an operand")
            if instruction.kind == "print":
                if instruction.result is not None or len(instruction.operands) != 1:
                    raise MirContractError("print instructions require one operand and no result")
            if instruction.kind == "construct":
                if instruction.result is None or not instruction.symbol:
                    raise MirContractError("construct instructions require a result and a symbol")
            if instruction.kind == "load_field":
                if instruction.result is None or len(instruction.operands) != 1 or not instruction.symbol:
                    raise MirContractError("load_field instructions require one operand, a result, and a symbol")
        for operand in block.terminator.operands:
            if operand not in local_set:
                raise MirContractError(f"terminator reads unknown local {operand}")
        for target in block.terminator.targets:
            if target not in block_set:
                raise MirContractError(f"terminator references unknown block {target}")
    _validate_reachable_blocks(blocks, entry_block)


def _validate_reachable(function: MirFunction) -> None:
    _validate_reachable_blocks(function.blocks, function.entry_block)


def _validate_reachable_blocks(blocks: tuple[MirBlock, ...], entry_block: int) -> None:
    by_id = {block.block_id: block for block in blocks}
    reachable: set[int] = set()
    pending = [entry_block]
    while pending:
        block_id = pending.pop()
        if block_id in reachable:
            continue
        reachable.add(block_id)
        pending.extend(by_id[block_id].terminator.targets)
    if reachable != set(by_id):
        missing = sorted(set(by_id) - reachable)
        raise MirContractError(f"unreachable MIR blocks: {missing}")


def canonical_mir_json(module: MirModule) -> str:
    return json.dumps(module.to_data(), sort_keys=True, separators=(",", ":"))


def _parse_span(data: object | None) -> SourceSpan | None:
    if data is None:
        return None
    if not isinstance(data, list) or len(data) != 2 or not all(isinstance(value, int) for value in data):
        raise MirContractError("MIR spans must be [start, length]")
    return SourceSpan(data[0], data[1])


def parse_mir_type(data: object) -> MirType:
    if not isinstance(data, Mapping):
        raise MirContractError("MIR type must be an object")
    name = data.get("name")
    arguments = data.get("arguments", [])
    if not isinstance(name, str) or not name:
        raise MirContractError("MIR type name must be non-empty")
    if not isinstance(arguments, list):
        raise MirContractError("MIR type arguments must be a list")
    return MirType(name, tuple(parse_mir_type(argument) for argument in arguments))


def _parse_executable(
    raw_executable: Mapping[str, object], label: str
) -> tuple[tuple[MirLocal, ...], tuple[MirBlock, ...], int]:
    locals_data = raw_executable.get("locals")
    blocks_data = raw_executable.get("blocks")
    if not isinstance(locals_data, list) or not isinstance(blocks_data, list):
        raise MirContractError(f"{label} locals and blocks must be lists")
    locals_: list[MirLocal] = []
    for raw in locals_data:
        if not isinstance(raw, Mapping):
            raise MirContractError("local entries must be objects")
        source_binding = raw.get("source_binding_id")
        locals_.append(MirLocal(
            int(raw.get("id", -1)), str(raw.get("name", "")), parse_mir_type(raw.get("type")),
            bool(raw.get("mutable", False)), str(raw.get("ownership", "value")),
            None if source_binding is None else int(source_binding),
        ))
    blocks: list[MirBlock] = []
    for raw_block in blocks_data:
        if not isinstance(raw_block, Mapping):
            raise MirContractError("block entries must be objects")
        instructions_data = raw_block.get("instructions")
        terminator_data = raw_block.get("terminator")
        if not isinstance(instructions_data, list) or not isinstance(terminator_data, Mapping):
            raise MirContractError("blocks require instruction lists and terminator objects")
        instructions: list[MirInstruction] = []
        for raw in instructions_data:
            if not isinstance(raw, Mapping):
                raise MirContractError("instruction entries must be objects")
            operands = raw.get("operands", [])
            caps = raw.get("capabilities", [])
            specialization = raw.get("specialization", [])
            if not isinstance(operands, list) or not all(isinstance(value, int) for value in operands):
                raise MirContractError("instruction operands must be integer lists")
            if not isinstance(caps, list) or not all(isinstance(value, str) for value in caps):
                raise MirContractError("instruction capabilities must be string lists")
            if not isinstance(specialization, list):
                raise MirContractError("instruction specialization must be a type list")
            result = raw.get("result")
            instructions.append(MirInstruction(
                int(raw.get("id", -1)), str(raw.get("kind", "")),
                None if result is None else int(result), tuple(operands),
                raw.get("symbol") if isinstance(raw.get("symbol"), str) else None,
                raw.get("value"), _parse_span(raw.get("span")), str(raw.get("ownership", "none")),
                str(raw.get("numeric_policy", "none")), str(raw.get("conversion_policy", "none")),
                str(raw.get("contract_kind", "none")), tuple(caps),
                tuple(parse_mir_type(argument) for argument in specialization),
            ))
        term_operands = terminator_data.get("operands", [])
        targets = terminator_data.get("targets", [])
        cases = terminator_data.get("cases", [])
        if not all(isinstance(values, list) and all(isinstance(value, int) for value in values) for values in (term_operands, targets, cases)):
            raise MirContractError("terminator operands, targets, and cases must be integer lists")
        terminator = MirTerminator(
            str(terminator_data.get("kind", "")), tuple(term_operands), tuple(targets), tuple(cases),
            _parse_span(terminator_data.get("span")),
        )
        blocks.append(MirBlock(int(raw_block.get("id", -1)), tuple(instructions), terminator))
    return tuple(locals_), tuple(blocks), int(raw_executable.get("entry_block", -1))


def parse_mir(data: Mapping[str, object]) -> MirModule:
    if data.get("schema") != MIR_SCHEMA:
        raise MirContractError(f"expected MIR schema {MIR_SCHEMA!r}")
    name = data.get("name")
    functions_data = data.get("functions")
    if not isinstance(name, str) or not name:
        raise MirContractError("module name must be non-empty")
    if not isinstance(functions_data, list):
        raise MirContractError("functions must be a list")
    destructors_data = data.get("destructors", [])
    if not isinstance(destructors_data, list):
        raise MirContractError("destructors must be a list")
    functions: list[MirFunction] = []
    for raw_function in functions_data:
        if not isinstance(raw_function, Mapping):
            raise MirContractError("function entries must be objects")
        capabilities = raw_function.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
            raise MirContractError("function capabilities must be strings")
        locals_, blocks, entry_block = _parse_executable(raw_function, "function")
        parameters_data = raw_function.get("parameters", [])
        if not isinstance(parameters_data, list):
            raise MirContractError("function parameters must be a list")
        parameters: list[MirParameter] = []
        for raw_parameter in parameters_data:
            if not isinstance(raw_parameter, Mapping):
                raise MirContractError("function parameter entries must be objects")
            parameters.append(MirParameter(
                int(raw_parameter.get("local", -1)), str(raw_parameter.get("mode", "value"))
            ))
        raw_origin = raw_function.get("borrowed_origin")
        functions.append(MirFunction(
            str(raw_function.get("name", "")), parse_mir_type(raw_function.get("return_type")),
            locals_, blocks, entry_block, tuple(capabilities), tuple(parameters),
            str(raw_function.get("return_mode", "value")),
            None if raw_origin is None else int(raw_origin),
        ))
    destructors: list[MirDestructor] = []
    for raw_destructor in destructors_data:
        if not isinstance(raw_destructor, Mapping):
            raise MirContractError("destructor entries must be objects")
        locals_, blocks, entry_block = _parse_executable(raw_destructor, "destructor")
        destructors.append(MirDestructor(
            parse_mir_type(raw_destructor.get("target")), locals_, blocks, entry_block,
        ))
    return MirModule(name, tuple(functions), destructors=tuple(destructors))


def load_mir_json(text: str) -> MirModule:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise MirContractError(f"invalid MIR JSON: {error}") from error
    if not isinstance(data, Mapping):
        raise MirContractError("MIR root must be an object")
    return parse_mir(data)
