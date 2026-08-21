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

    def __post_init__(self) -> None:
        if not self.name:
            raise MirContractError("function names must be non-empty")
        if self.entry_block < 0:
            raise MirContractError("entry block IDs must be non-negative")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise MirContractError("function capability requirements must be unique")
        if any(not capability for capability in self.capabilities):
            raise MirContractError("function capability names must be non-empty")
        _validate_function(self)

    def to_data(self) -> dict[str, object]:
        return {
            "name": self.name,
            "return_type": self.return_type.to_data(),
            "locals": [local.to_data() for local in self.locals],
            "blocks": [block.to_data() for block in self.blocks],
            "entry_block": self.entry_block,
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True, slots=True)
class MirModule:
    name: str
    functions: tuple[MirFunction, ...]
    schema: str = MIR_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MIR_SCHEMA:
            raise MirContractError(f"expected MIR schema {MIR_SCHEMA!r}")
        if not self.name:
            raise MirContractError("module name must be non-empty")
        names = [function.name for function in self.functions]
        if len(set(names)) != len(names):
            raise MirContractError("duplicate MIR function name")

    def to_data(self) -> dict[str, object]:
        return {"schema": self.schema, "name": self.name, "functions": [function.to_data() for function in self.functions]}


def _validate_function(function: MirFunction) -> None:
    local_ids = [local.local_id for local in function.locals]
    block_ids = [block.block_id for block in function.blocks]
    instruction_ids = [instruction.instruction_id for block in function.blocks for instruction in block.instructions]
    if len(set(local_ids)) != len(local_ids):
        raise MirContractError("duplicate MIR local ID")
    if len(set(block_ids)) != len(block_ids):
        raise MirContractError("duplicate MIR block ID")
    if len(set(instruction_ids)) != len(instruction_ids):
        raise MirContractError("duplicate MIR instruction ID")
    local_set = set(local_ids)
    block_set = set(block_ids)
    if function.entry_block not in block_set:
        raise MirContractError("entry block does not exist")
    for block in function.blocks:
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
    _validate_reachable(function)


def _validate_reachable(function: MirFunction) -> None:
    by_id = {block.block_id: block for block in function.blocks}
    reachable: set[int] = set()
    pending = [function.entry_block]
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


def parse_mir(data: Mapping[str, object]) -> MirModule:
    if data.get("schema") != MIR_SCHEMA:
        raise MirContractError(f"expected MIR schema {MIR_SCHEMA!r}")
    name = data.get("name")
    functions_data = data.get("functions")
    if not isinstance(name, str) or not name:
        raise MirContractError("module name must be non-empty")
    if not isinstance(functions_data, list):
        raise MirContractError("functions must be a list")
    functions: list[MirFunction] = []
    for raw_function in functions_data:
        if not isinstance(raw_function, Mapping):
            raise MirContractError("function entries must be objects")
        locals_data = raw_function.get("locals")
        blocks_data = raw_function.get("blocks")
        capabilities = raw_function.get("capabilities", [])
        if not isinstance(locals_data, list) or not isinstance(blocks_data, list):
            raise MirContractError("function locals and blocks must be lists")
        if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
            raise MirContractError("function capabilities must be strings")
        locals_: list[MirLocal] = []
        for raw in locals_data:
            if not isinstance(raw, Mapping):
                raise MirContractError("local entries must be objects")
            source_binding = raw.get("source_binding_id")
            locals_.append(MirLocal(int(raw.get("id", -1)), str(raw.get("name", "")), parse_mir_type(raw.get("type")), bool(raw.get("mutable", False)), str(raw.get("ownership", "value")), None if source_binding is None else int(source_binding)))
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
                instructions.append(MirInstruction(int(raw.get("id", -1)), str(raw.get("kind", "")), None if result is None else int(result), tuple(operands), raw.get("symbol") if isinstance(raw.get("symbol"), str) else None, raw.get("value"), _parse_span(raw.get("span")), str(raw.get("ownership", "none")), str(raw.get("numeric_policy", "none")), str(raw.get("conversion_policy", "none")), str(raw.get("contract_kind", "none")), tuple(caps), tuple(parse_mir_type(argument) for argument in specialization)))
            term_operands = terminator_data.get("operands", [])
            targets = terminator_data.get("targets", [])
            cases = terminator_data.get("cases", [])
            if not all(isinstance(values, list) and all(isinstance(value, int) for value in values) for values in (term_operands, targets, cases)):
                raise MirContractError("terminator operands, targets, and cases must be integer lists")
            terminator = MirTerminator(str(terminator_data.get("kind", "")), tuple(term_operands), tuple(targets), tuple(cases), _parse_span(terminator_data.get("span")))
            blocks.append(MirBlock(int(raw_block.get("id", -1)), tuple(instructions), terminator))
        functions.append(MirFunction(str(raw_function.get("name", "")), parse_mir_type(raw_function.get("return_type")), tuple(locals_), tuple(blocks), int(raw_function.get("entry_block", -1)), tuple(capabilities)))
    return MirModule(name, tuple(functions))


def load_mir_json(text: str) -> MirModule:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise MirContractError(f"invalid MIR JSON: {error}") from error
    if not isinstance(data, Mapping):
        raise MirContractError("MIR root must be an object")
    return parse_mir(data)
