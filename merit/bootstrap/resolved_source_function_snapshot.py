"""Versioned handoff from Merit-native resolved source assembly to canonical MIR.

The native replacement pipeline owns source interpretation, clause resolution,
ownership, instruction provenance, CFG construction, and placement.  This module
only decodes the stable integer snapshot produced by integration probes and
passes the already-resolved records to the ownership-aware bootstrap-mir-v1
materializer.  It deliberately performs no source/HIR/ownership re-lowering.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from merit.bootstrap.mir_contract import MirDestructor, MirModule, MirType
from merit.bootstrap.mir_function_assembly_parity import (
    BODY_INSTRUCTION_KINDS,
    BODY_INSTRUCTION_SOURCE_KIND,
    lower_native_whole_function_assembly,
)
from merit.bootstrap.mir_function_ownership_assembly_parity import (
    lower_native_ownership_whole_function_assembly,
)

SNAPSHOT_MAGIC = 0x4D525346  # "MRSF"
SNAPSHOT_VERSION = 9
_TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT = 1
_TYPE_DESCRIPTOR_OWNED_PAYLOAD_ENUM = 2
_TYPE_DESCRIPTOR_AGGREGATE_STRUCT = 3
_TYPE_DESCRIPTOR_VECTOR = 4
_OWNED_FIELD_STRUCT_TYPE_BASE = 1_000_000
_OWNED_PAYLOAD_ENUM_TYPE_BASE = 1_100_000
_AGGREGATE_STRUCT_TYPE_BASE = 1_200_000
_DECIMAL_TYPE_BASE = 1_300_000
_BOUNDED_TYPE_BASE = 1_400_000
_VECTOR_TYPE_BASE = 1_500_000
_NUMERIC_DESCRIPTOR_DECIMAL = 1
_NUMERIC_DESCRIPTOR_BOUNDED = 2
_NUMERIC_DESCRIPTOR_LIMB_BASE = 1_000_000_000
_COPY_PAYLOAD_ENUM_TYPE_BASE = 1_000
_I64_STRUCT_TYPE_BASE = 2_000
_DESTRUCTOR_I64_STRUCT_TYPE_BASE = 3_000
_LEGACY_OWNED_PAYLOAD_ENUM_TYPE_BASE = 4_000
_SECTION_WIDTHS_BY_VERSION = {
    1: (16, 12, 5, 8, 4, 8, 7, 3, 1),
    2: (16, 12, 5, 8, 4, 8, 7, 3, 1, 5),
    3: (16, 12, 5, 8, 4, 8, 7, 3, 1, 5),
    4: (16, 12, 5, 8, 4, 8, 7, 3, 1, 5, 7, 16, 7, 3),
    5: (16, 12, 5, 8, 4, 8, 7, 3, 1, 6, 7, 16, 7, 3),
    6: (16, 12, 5, 8, 4, 8, 7, 3, 1, 6, 11, 7, 16, 7, 3),
    7: (16, 12, 5, 8, 4, 8, 7, 3, 1, 6, 11, 7, 16, 7, 3, 1),
    8: (16, 12, 5, 8, 4, 8, 7, 3, 1, 6, 11, 7, 16, 7, 3, 1),
    9: (16, 12, 5, 8, 4, 8, 7, 3, 1, 11, 11, 7, 16, 7, 3, 1),
}
SNAPSHOT_SECTION_COUNT = len(_SECTION_WIDTHS_BY_VERSION[SNAPSHOT_VERSION])


@dataclass(frozen=True)
class ResolvedSourceDestructorSnapshot:
    type_code: int
    body_records: tuple[tuple[int, ...], ...]
    cfg_records: tuple[tuple[int, ...], ...]
    placements: tuple[tuple[int, ...], ...]


class ResolvedSourceFunctionSnapshotError(ValueError):
    """Raised when a resolved-source assembly snapshot is malformed."""


@dataclass(frozen=True)
class ResolvedSourceFunctionSnapshot:
    body_records: tuple[tuple[int, ...], ...]
    contract_records: tuple[tuple[int, ...], ...]
    contract_locals: tuple[tuple[int, ...], ...]
    instruction_sources: tuple[tuple[int, ...], ...]
    ownership_bindings: tuple[tuple[int, ...], ...]
    ownership_records: tuple[tuple[int, ...], ...]
    cfg_records: tuple[tuple[int, ...], ...]
    placements: tuple[tuple[int, ...], ...]
    capability_ids: tuple[int, ...]
    type_descriptors: tuple[tuple[int, ...], ...] = ()
    numeric_type_descriptors: tuple[tuple[int, ...], ...] = ()
    destructors: tuple[ResolvedSourceDestructorSnapshot, ...] = ()
    effective_source_bytes: tuple[int, ...] = ()
    exported: bool = False
    version: int = SNAPSHOT_VERSION


def decode_resolved_source_function_snapshot(values: Iterable[int]) -> ResolvedSourceFunctionSnapshot:
    data = tuple(int(value) for value in values)
    if len(data) < 2 or data[0] != SNAPSHOT_MAGIC:
        raise ResolvedSourceFunctionSnapshotError("resolved source snapshot has invalid magic")
    if data[1] not in _SECTION_WIDTHS_BY_VERSION:
        raise ResolvedSourceFunctionSnapshotError(
            f"unsupported resolved source snapshot version {data[1]}"
        )

    position = 2
    sections: list[tuple[tuple[int, ...], ...]] = []
    widths = _SECTION_WIDTHS_BY_VERSION[data[1]]
    for section_index, width in enumerate(widths):
        if position >= len(data):
            raise ResolvedSourceFunctionSnapshotError(
                f"resolved source snapshot is missing section {section_index}"
            )
        count = data[position]
        position += 1
        if count < 0:
            raise ResolvedSourceFunctionSnapshotError(
                f"resolved source snapshot section {section_index} has negative count"
            )
        end = position + count * width
        if end > len(data):
            raise ResolvedSourceFunctionSnapshotError(
                f"resolved source snapshot section {section_index} is truncated"
            )
        rows = tuple(
            tuple(data[offset : offset + width])
            for offset in range(position, end, width)
        )
        sections.append(rows)
        position = end

    if position != len(data):
        raise ResolvedSourceFunctionSnapshotError("resolved source snapshot has trailing data")

    capabilities = tuple(row[0] for row in sections[8])
    destructor_snapshots: list[ResolvedSourceDestructorSnapshot] = []
    destructor_section = 11 if data[1] >= 6 else 10
    destructor_body_section = destructor_section + 1
    destructor_cfg_section = destructor_section + 2
    destructor_placement_section = destructor_section + 3
    if len(sections) > destructor_section:
        body_cursor = cfg_cursor = placement_cursor = 0
        destructor_types: set[int] = set()
        for index, row in enumerate(sections[destructor_section]):
            type_code, body_start, body_count, cfg_start, cfg_count, placement_start, placement_count = row
            if type_code <= 0 or min(body_start, body_count, cfg_start, cfg_count, placement_start, placement_count) < 0:
                raise ResolvedSourceFunctionSnapshotError(f"destructor descriptor {index} is invalid")
            if (body_start, cfg_start, placement_start) != (body_cursor, cfg_cursor, placement_cursor):
                raise ResolvedSourceFunctionSnapshotError(f"destructor descriptor {index} is noncanonical")
            if type_code in destructor_types:
                raise ResolvedSourceFunctionSnapshotError(
                    f"destructor descriptor {index} duplicates target type {type_code}"
                )
            destructor_types.add(type_code)
            body_cursor += body_count
            cfg_cursor += cfg_count
            placement_cursor += placement_count
            if body_cursor > len(sections[destructor_body_section]) or cfg_cursor > len(sections[destructor_cfg_section]) or placement_cursor > len(sections[destructor_placement_section]):
                raise ResolvedSourceFunctionSnapshotError(f"destructor descriptor {index} exceeds its record sections")
            destructor_snapshots.append(ResolvedSourceDestructorSnapshot(
                type_code,
                sections[destructor_body_section][body_start:body_cursor],
                sections[destructor_cfg_section][cfg_start:cfg_cursor],
                sections[destructor_placement_section][placement_start:placement_cursor],
            ))
        if (body_cursor, cfg_cursor, placement_cursor) != (
            len(sections[destructor_body_section]),
            len(sections[destructor_cfg_section]),
            len(sections[destructor_placement_section]),
        ):
            raise ResolvedSourceFunctionSnapshotError("destructor record sections contain unreferenced rows")

    if data[1] >= 8 and sections[0]:
        if sections[0][0][13] not in {0, 1}:
            raise ResolvedSourceFunctionSnapshotError(
                "resolved source snapshot has invalid export metadata"
            )
        exported = sections[0][0][13] == 1
    else:
        exported = False

    return ResolvedSourceFunctionSnapshot(
        body_records=sections[0],
        contract_records=sections[1],
        contract_locals=sections[2],
        instruction_sources=sections[3],
        ownership_bindings=sections[4],
        ownership_records=sections[5],
        cfg_records=sections[6],
        placements=sections[7],
        capability_ids=capabilities,
        type_descriptors=sections[9] if len(sections) > 9 else (),
        numeric_type_descriptors=sections[10] if data[1] >= 6 else (),
        destructors=tuple(destructor_snapshots),
        effective_source_bytes=tuple(row[0] for row in sections[15]) if data[1] >= 7 else (),
        exported=exported,
        version=data[1],
    )


def _descriptor_type_names(
    rows: tuple[tuple[int, ...], ...], *, version: int = 2,
    known_types: Mapping[int, MirType] | None = None,
    source: str = "",
) -> dict[int, MirType]:
    raw: dict[int, tuple[int, int, int, int]] = {}
    aggregate_fields: dict[int, list[int]] = {}
    aggregate_policies: dict[int, int] = {}
    enum_fields: dict[int, list[int]] = {}
    aggregate_abi: dict[int, tuple[int, str, list[str]]] = {}
    for index, row in enumerate(rows):
        if version >= 9:
            (
                code, kind, identity, child_code, destructor_policy, ordinal,
                name_start, name_length, member_start, member_length, abi_flags,
            ) = row
            if min(name_start, name_length, member_start, member_length) < 0 or abi_flags not in {0, 1, 2, 3}:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has invalid ABI metadata"
                )
        elif version >= 5:
            code, kind, identity, child_code, destructor_policy, ordinal = row
            name_start = name_length = member_start = member_length = abi_flags = 0
        else:
            code, kind, identity, child_code, destructor_policy = row
            ordinal = 0
            name_start = name_length = member_start = member_length = abi_flags = 0
        if code <= 0 or identity < 0 or child_code <= 0 or kind not in {
            _TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT,
            _TYPE_DESCRIPTOR_OWNED_PAYLOAD_ENUM,
            *({_TYPE_DESCRIPTOR_AGGREGATE_STRUCT} if version >= 3 else set()),
            *({_TYPE_DESCRIPTOR_VECTOR} if version >= 7 else set()),
        }:
            raise ResolvedSourceFunctionSnapshotError(f"type descriptor {index} is invalid")
        if kind == _TYPE_DESCRIPTOR_AGGREGATE_STRUCT:
            if destructor_policy not in {0, 1}:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has unsupported destructor policy"
                )
            expected_code = _AGGREGATE_STRUCT_TYPE_BASE + identity
            if code != expected_code:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has noncanonical type code"
                )
            if code in raw:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} conflicts with another descriptor kind"
                )
            fields = aggregate_fields.setdefault(code, [])
            if version >= 5 and ordinal != len(fields):
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has noncanonical field ordinal"
                )
            if code in aggregate_policies and destructor_policy:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has duplicate destructor policy"
                )
            if destructor_policy:
                aggregate_policies[code] = len(fields)
            fields.append(child_code)
            if version >= 9:
                def span_text(start: int, length: int, label: str) -> str:
                    end = start + length
                    source_bytes = source.encode("utf-8")
                    if length <= 0 or end > len(source_bytes):
                        raise ResolvedSourceFunctionSnapshotError(
                            f"type descriptor {index} has invalid {label} span"
                        )
                    try:
                        value = source_bytes[start:end].decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise ResolvedSourceFunctionSnapshotError(
                            f"type descriptor {index} has invalid {label} UTF-8"
                        ) from exc
                    if not value.isidentifier():
                        raise ResolvedSourceFunctionSnapshotError(
                            f"type descriptor {index} has invalid {label} identifier"
                        )
                    return value

                type_name = span_text(name_start, name_length, "type-name")
                member_name = span_text(member_start, member_length, "member-name")
                prior = aggregate_abi.get(code)
                if prior is None:
                    aggregate_abi[code] = (abi_flags, type_name, [member_name])
                else:
                    prior_flags, prior_name, members = prior
                    if (prior_flags, prior_name) != (abi_flags, type_name):
                        raise ResolvedSourceFunctionSnapshotError(
                            f"type descriptor {index} has inconsistent ABI identity"
                        )
                    members.append(member_name)
            continue
        if kind == _TYPE_DESCRIPTOR_OWNED_PAYLOAD_ENUM and version >= 5:
            if destructor_policy != 0:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has unsupported destructor policy"
                )
            expected_code = _OWNED_PAYLOAD_ENUM_TYPE_BASE + identity
            if code != expected_code:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has noncanonical type code"
                )
            if code in raw or code in aggregate_fields:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} conflicts with another descriptor kind"
                )
            variants = enum_fields.setdefault(code, [])
            if ordinal != len(variants):
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has noncanonical variant ordinal"
                )
            variants.append(child_code)
            continue
        if kind == _TYPE_DESCRIPTOR_VECTOR:
            if destructor_policy != 0 or ordinal != 0:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has invalid vector metadata"
                )
            expected_code = _VECTOR_TYPE_BASE + identity
            if code != expected_code:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} has noncanonical type code"
                )
            if code in raw or code in aggregate_fields or code in enum_fields:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type descriptor {index} conflicts with another descriptor kind"
                )
            raw[code] = (kind, identity, child_code, destructor_policy)
            continue
        if destructor_policy != 0:
            raise ResolvedSourceFunctionSnapshotError(
                f"type descriptor {index} has unsupported destructor policy"
            )
        if code in raw or code in aggregate_fields:
            raise ResolvedSourceFunctionSnapshotError(f"duplicate type descriptor code {code}")
        expected_code = (
            _OWNED_FIELD_STRUCT_TYPE_BASE + identity
            if kind == _TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT
            else _OWNED_PAYLOAD_ENUM_TYPE_BASE + identity
        )
        if code != expected_code:
            raise ResolvedSourceFunctionSnapshotError(
                f"type descriptor {index} has noncanonical type code"
            )
        raw[code] = (kind, identity, child_code, destructor_policy)

    for code in (*aggregate_fields, *enum_fields):
        if code in raw:
            raise ResolvedSourceFunctionSnapshotError(f"duplicate type descriptor code {code}")

    resolved: dict[int, MirType] = {
        1: MirType("i64"),
        2: MirType("bool"),
        3: MirType("Allocator"),
        4: MirType("Buffer"),
        5: MirType("i8"),
        6: MirType("i16"),
        7: MirType("i32"),
        8: MirType("u8"),
        9: MirType("u16"),
        10: MirType("u32"),
        11: MirType("u64"),
        12: MirType("String"),
        13: MirType("ByteSlice"),
        14: MirType("unit"),
    }
    if known_types:
        for code, type_ in known_types.items():
            if code in resolved and resolved[code] != type_:
                raise ResolvedSourceFunctionSnapshotError(
                    f"known type code {code} conflicts with a builtin type"
                )
            resolved[code] = type_

    def resolve(code: int, active: frozenset[int]) -> MirType:
        if code in resolved:
            return resolved[code]
        if _COPY_PAYLOAD_ENUM_TYPE_BASE <= code < _I64_STRUCT_TYPE_BASE:
            return MirType(f"enum_copy_payload_{code - _COPY_PAYLOAD_ENUM_TYPE_BASE}")
        if _I64_STRUCT_TYPE_BASE <= code < _DESTRUCTOR_I64_STRUCT_TYPE_BASE:
            return MirType(f"struct_i64_{code - _I64_STRUCT_TYPE_BASE}")
        if _DESTRUCTOR_I64_STRUCT_TYPE_BASE <= code < _LEGACY_OWNED_PAYLOAD_ENUM_TYPE_BASE:
            return MirType(f"struct_i64_destructor_{code - _DESTRUCTOR_I64_STRUCT_TYPE_BASE}")
        descriptor = raw.get(code)
        aggregate = aggregate_fields.get(code)
        enum_variants = enum_fields.get(code)
        if enum_variants is not None:
            if code in active:
                raise ResolvedSourceFunctionSnapshotError("type descriptor graph is cyclic")
            identity = code - _OWNED_PAYLOAD_ENUM_TYPE_BASE
            children = tuple(resolve(child, active | {code}) for child in enum_variants)
            if not children:
                raise ResolvedSourceFunctionSnapshotError("enum type descriptor has no variants")
            result = MirType(f"enum_owned_payload_{identity}", children)
            resolved[code] = result
            return result
        if aggregate is not None:
            if code in active:
                raise ResolvedSourceFunctionSnapshotError("type descriptor graph is cyclic")
            identity = code - _AGGREGATE_STRUCT_TYPE_BASE
            children = tuple(resolve(child, active | {code}) for child in aggregate)
            if not children:
                raise ResolvedSourceFunctionSnapshotError("aggregate type descriptor has no fields")
            policy = aggregate_policies.get(code, -1)
            name = f"struct_aggregate_{identity}_destructor_{policy}"
            abi = aggregate_abi.get(code)
            if abi is not None:
                flags, type_name, members = abi
                encoded = "_".join(value.encode("utf-8").hex() for value in (type_name, *members))
                name = f"{name}__abi_{flags}_{encoded}"
            result = MirType(name, children)
            resolved[code] = result
            return result
        if descriptor is None:
            raise ResolvedSourceFunctionSnapshotError(
                f"type descriptor references unresolved child code {code}"
            )
        if code in active:
            raise ResolvedSourceFunctionSnapshotError("type descriptor graph is cyclic")
        kind, identity, child_code, _ = descriptor
        child = resolve(child_code, active | {code})
        if kind == _TYPE_DESCRIPTOR_VECTOR:
            result = MirType("Vec", (child,))
        else:
            name = (
                "struct_owned_field"
                if kind == _TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT
                else "enum_owned_payload"
            )
            result = MirType(f"{name}_{identity}", (child,))
        resolved[code] = result
        return result

    for code in (*raw, *aggregate_fields, *enum_fields):
        resolve(code, frozenset())
    return {code: resolved[code] for code in (*raw, *aggregate_fields, *enum_fields)}


def _numeric_descriptor_type_names(rows: tuple[tuple[int, ...], ...]) -> dict[int, MirType]:
    result: dict[int, MirType] = {}
    identities: set[tuple[int, int]] = set()
    for index, row in enumerate(rows):
        (
            code, kind, identity, base_code,
            lower_sign, lower_high, lower_low,
            upper_sign, upper_high, upper_low, policy,
        ) = row
        if identity < 0 or (kind, identity) in identities or code in result:
            raise ResolvedSourceFunctionSnapshotError(f"numeric type descriptor {index} is duplicate or invalid")
        identities.add((kind, identity))
        if kind == _NUMERIC_DESCRIPTOR_DECIMAL:
            if (
                code != _DECIMAL_TYPE_BASE + identity or base_code != 0
                or lower_sign != 0 or upper_sign != 0 or upper_high != 0 or upper_low != 0
            ):
                raise ResolvedSourceFunctionSnapshotError(f"decimal type descriptor {index} is noncanonical")
            if lower_high < 1 or lower_low < 0 or lower_low > lower_high or policy not in range(5):
                raise ResolvedSourceFunctionSnapshotError(f"decimal type descriptor {index} has invalid policy")
            result[code] = MirType(f"decimal_{identity}_{lower_high}_{lower_low}_{policy}")
        elif kind == _NUMERIC_DESCRIPTOR_BOUNDED:
            if code != _BOUNDED_TYPE_BASE + identity or base_code not in {5, 6, 7, 1, 8, 9, 10, 11}:
                raise ResolvedSourceFunctionSnapshotError(f"bounded type descriptor {index} is noncanonical")
            limbs = (lower_high, lower_low, upper_high, upper_low)
            if (
                lower_sign not in {-1, 0, 1} or upper_sign not in {-1, 0, 1}
                or any(value < 0 for value in limbs)
                or lower_low >= _NUMERIC_DESCRIPTOR_LIMB_BASE
                or upper_low >= _NUMERIC_DESCRIPTOR_LIMB_BASE
                or (lower_sign == 0) != (lower_high == 0 and lower_low == 0)
                or (upper_sign == 0) != (upper_high == 0 and upper_low == 0)
                or policy != 0
            ):
                raise ResolvedSourceFunctionSnapshotError(f"bounded type descriptor {index} has invalid range")
            lower = lower_sign * (lower_high * _NUMERIC_DESCRIPTOR_LIMB_BASE + lower_low)
            upper = upper_sign * (upper_high * _NUMERIC_DESCRIPTOR_LIMB_BASE + upper_low)
            if lower > upper:
                raise ResolvedSourceFunctionSnapshotError(f"bounded type descriptor {index} has invalid range")
            result[code] = MirType(
                f"bounded_{identity}_{base_code}_{lower}_{upper}",
                (MirType({5: "i8", 6: "i16", 7: "i32", 1: "i64", 8: "u8", 9: "u16", 10: "u32", 11: "u64"}[base_code]),),
            )
        else:
            raise ResolvedSourceFunctionSnapshotError(f"numeric type descriptor {index} has unknown kind")
    return result


def materialize_resolved_source_function_snapshot(
    *,
    source: str,
    module_name: str,
    snapshot: ResolvedSourceFunctionSnapshot,
    capability_names: Mapping[int, str],
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    """Materialize a decoded native snapshot as canonical bootstrap-mir-v1."""

    effective_source = source
    if snapshot.effective_source_bytes:
        if any(value < 0 or value > 255 for value in snapshot.effective_source_bytes):
            raise ResolvedSourceFunctionSnapshotError(
                "resolved source snapshot contains an invalid effective-source byte"
            )
        try:
            effective_source = bytes(snapshot.effective_source_bytes).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ResolvedSourceFunctionSnapshotError(
                "resolved source snapshot effective source is not UTF-8"
            ) from exc

    numeric_names = _numeric_descriptor_type_names(snapshot.numeric_type_descriptors)
    descriptor_names = _descriptor_type_names(
        snapshot.type_descriptors, version=snapshot.version, known_types=numeric_names,
        source=effective_source,
    )
    if descriptor_names.keys() & numeric_names.keys():
        raise ResolvedSourceFunctionSnapshotError("numeric and aggregate type descriptors conflict")
    descriptor_names.update(numeric_names)
    if type_names:
        for code, type_ in type_names.items():
            if code in descriptor_names and descriptor_names[code] != type_:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type name for code {code} conflicts with native descriptor"
                )
        descriptor_names.update(type_names)
    function_module = lower_native_ownership_whole_function_assembly(
        source=effective_source,
        module_name=module_name,
        body_records=snapshot.body_records,
        contract_records=snapshot.contract_records,
        contract_locals=snapshot.contract_locals,
        instruction_sources=snapshot.instruction_sources,
        ownership_bindings=snapshot.ownership_bindings,
        ownership_records=snapshot.ownership_records,
        cfg_records=snapshot.cfg_records,
        placements=snapshot.placements,
        capability_ids=snapshot.capability_ids,
        capability_names=capability_names,
        type_names=descriptor_names,
    )
    destructors: list[MirDestructor] = []
    for index, raw in enumerate(snapshot.destructors):
        target = descriptor_names.get(raw.type_code)
        if target is None and _DESTRUCTOR_I64_STRUCT_TYPE_BASE <= raw.type_code < _LEGACY_OWNED_PAYLOAD_ENUM_TYPE_BASE:
            target = MirType(f"struct_i64_destructor_{raw.type_code - _DESTRUCTOR_I64_STRUCT_TYPE_BASE}")
        if target is None:
            raise ResolvedSourceFunctionSnapshotError(
                f"destructor descriptor {index} references unresolved type code {raw.type_code}"
            )
        lowered = lower_native_whole_function_assembly(
            source=effective_source,
            module_name=module_name,
            body_records=raw.body_records,
            contract_records=(),
            contract_locals=(),
            instruction_sources=tuple(
                (row[3], BODY_INSTRUCTION_SOURCE_KIND, row[3], 0, -1, row[4], row[5], row[6])
                for row in raw.body_records
                if row[0] in BODY_INSTRUCTION_KINDS
            ),
            cfg_records=raw.cfg_records,
            placements=raw.placements,
            capability_ids=(),
            capability_names={},
            type_names=descriptor_names,
        ).functions[0]
        if not lowered.locals or lowered.locals[0].type != target:
            raise ResolvedSourceFunctionSnapshotError(
                f"destructor descriptor {index} has invalid self local"
            )
        self_local = replace(
            lowered.locals[0], name="self", mutable=True, ownership="mutable_borrow"
        )
        destructors.append(MirDestructor(
            target, (self_local, *lowered.locals[1:]), lowered.blocks, lowered.entry_block
        ))
    function = replace(function_module.functions[0], exported=snapshot.exported)
    return MirModule(
        function_module.name,
        (function,),
        destructors=tuple(destructors),
    )
