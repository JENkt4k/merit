"""Versioned scalar call ABI layered over ``bootstrap-mir-v1``.

The core MIR contract intentionally stabilized before parameter passing. This
module adds an explicit, independently versioned function-signature layer
without changing the serialized bootstrap-mir-v1 graph. Parameters bind, in
source order, to existing MIR locals at function entry.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from merit.bootstrap.mir_contract import MirModule, MirType

MIR_ABI_SCHEMA = "bootstrap-mir-abi-v1"
PARAMETER_OWNERSHIP = frozenset({"value", "owned", "borrowed", "mutable_borrow"})


class MirAbiError(ValueError):
    """Raised when a MIR module/signature set violates the scalar ABI."""


@dataclass(frozen=True, slots=True)
class MirParameter:
    name: str
    local_id: int
    type: MirType
    ownership: str = "value"
    mutable: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise MirAbiError("parameter names must be non-empty")
        if self.local_id < 0:
            raise MirAbiError("parameter local IDs must be non-negative")
        if self.ownership not in PARAMETER_OWNERSHIP:
            raise MirAbiError(f"unsupported parameter ownership: {self.ownership}")
        if self.mutable and self.ownership == "borrowed":
            raise MirAbiError("immutable borrowed parameters cannot be mutable")

    def to_data(self) -> dict[str, object]:
        return {
            "name": self.name,
            "local_id": self.local_id,
            "type": self.type.to_data(),
            "ownership": self.ownership,
            "mutable": self.mutable,
        }


@dataclass(frozen=True, slots=True)
class MirFunctionSignature:
    function: str
    parameters: tuple[MirParameter, ...] = ()
    exported_name: str | None = None

    def __post_init__(self) -> None:
        if not self.function:
            raise MirAbiError("signature function names must be non-empty")
        names = [parameter.name for parameter in self.parameters]
        local_ids = [parameter.local_id for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise MirAbiError(f"duplicate parameter name in {self.function}")
        if len(local_ids) != len(set(local_ids)):
            raise MirAbiError(f"duplicate parameter local ID in {self.function}")
        if self.exported_name == "":
            raise MirAbiError("exported names must be non-empty when present")

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "function": self.function,
            "parameters": [parameter.to_data() for parameter in self.parameters],
        }
        if self.exported_name is not None:
            data["exported_name"] = self.exported_name
        return data


@dataclass(frozen=True, slots=True)
class MirAbiModule:
    module: MirModule
    signatures: tuple[MirFunctionSignature, ...]
    schema: str = MIR_ABI_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MIR_ABI_SCHEMA:
            raise MirAbiError(f"expected ABI schema {MIR_ABI_SCHEMA!r}")
        _validate_abi(self)

    def signature_map(self) -> dict[str, MirFunctionSignature]:
        return {signature.function: signature for signature in self.signatures}

    def to_data(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "module": self.module.to_data(),
            "signatures": [signature.to_data() for signature in self.signatures],
        }


def _validate_abi(abi: MirAbiModule) -> None:
    functions = {function.name: function for function in abi.module.functions}
    signature_names = [signature.function for signature in abi.signatures]
    if len(signature_names) != len(set(signature_names)):
        raise MirAbiError("duplicate function signature")
    if set(signature_names) != set(functions):
        missing = sorted(set(functions) - set(signature_names))
        extra = sorted(set(signature_names) - set(functions))
        raise MirAbiError(
            f"signature set must exactly cover module functions; missing={missing}, extra={extra}"
        )
    exported = [
        signature.exported_name
        for signature in abi.signatures
        if signature.exported_name is not None
    ]
    if len(exported) != len(set(exported)):
        raise MirAbiError("duplicate exported C name")
    for signature in abi.signatures:
        function = functions[signature.function]
        locals_by_id = {local.local_id: local for local in function.locals}
        for parameter in signature.parameters:
            local = locals_by_id.get(parameter.local_id)
            if local is None:
                raise MirAbiError(
                    f"parameter {parameter.name} references unknown local {parameter.local_id}"
                )
            if local.type != parameter.type:
                raise MirAbiError(
                    f"parameter {parameter.name} type does not match local {parameter.local_id}"
                )
            if local.ownership != parameter.ownership:
                raise MirAbiError(
                    f"parameter {parameter.name} ownership does not match local {parameter.local_id}"
                )
            if local.mutable != parameter.mutable:
                raise MirAbiError(
                    f"parameter {parameter.name} mutability does not match local {parameter.local_id}"
                )


def canonical_mir_abi_json(abi: MirAbiModule) -> str:
    return json.dumps(abi.to_data(), sort_keys=True, separators=(",", ":"))


def parse_mir_abi(data: Mapping[str, object]) -> MirAbiModule:
    from merit.bootstrap.mir_contract import parse_mir, parse_mir_type

    if data.get("schema") != MIR_ABI_SCHEMA:
        raise MirAbiError(f"expected ABI schema {MIR_ABI_SCHEMA!r}")
    raw_module = data.get("module")
    raw_signatures = data.get("signatures")
    if not isinstance(raw_module, Mapping):
        raise MirAbiError("ABI module must be an object")
    if not isinstance(raw_signatures, list):
        raise MirAbiError("ABI signatures must be a list")
    signatures: list[MirFunctionSignature] = []
    for raw_signature in raw_signatures:
        if not isinstance(raw_signature, Mapping):
            raise MirAbiError("signature entries must be objects")
        function = raw_signature.get("function")
        parameters = raw_signature.get("parameters", [])
        exported_name = raw_signature.get("exported_name")
        if not isinstance(function, str) or not function:
            raise MirAbiError("signature function must be non-empty")
        if not isinstance(parameters, list):
            raise MirAbiError("signature parameters must be a list")
        if exported_name is not None and not isinstance(exported_name, str):
            raise MirAbiError("exported_name must be a string")
        parsed_parameters: list[MirParameter] = []
        for raw_parameter in parameters:
            if not isinstance(raw_parameter, Mapping):
                raise MirAbiError("parameter entries must be objects")
            name = raw_parameter.get("name")
            local_id = raw_parameter.get("local_id")
            ownership = raw_parameter.get("ownership", "value")
            mutable = raw_parameter.get("mutable", False)
            if not isinstance(name, str) or not isinstance(local_id, int):
                raise MirAbiError("parameter name/local_id are required")
            if not isinstance(ownership, str) or not isinstance(mutable, bool):
                raise MirAbiError("parameter ownership/mutable fields are invalid")
            parsed_parameters.append(
                MirParameter(
                    name,
                    local_id,
                    parse_mir_type(raw_parameter.get("type")),
                    ownership,
                    mutable,
                )
            )
        signatures.append(
            MirFunctionSignature(function, tuple(parsed_parameters), exported_name)
        )
    return MirAbiModule(parse_mir(raw_module), tuple(signatures))
