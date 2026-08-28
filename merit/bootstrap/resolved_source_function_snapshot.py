"""Versioned handoff from Merit-native resolved source assembly to canonical MIR.

The native replacement pipeline owns source interpretation, clause resolution,
ownership, instruction provenance, CFG construction, and placement.  This module
only decodes the stable integer snapshot produced by integration probes and
passes the already-resolved records to the ownership-aware bootstrap-mir-v1
materializer.  It deliberately performs no source/HIR/ownership re-lowering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from merit.bootstrap.mir_contract import MirModule, MirType
from merit.bootstrap.mir_function_ownership_assembly_parity import (
    lower_native_ownership_whole_function_assembly,
)

SNAPSHOT_MAGIC = 0x4D525346  # "MRSF"
SNAPSHOT_VERSION = 2
_TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT = 1
_TYPE_DESCRIPTOR_OWNED_PAYLOAD_ENUM = 2
_OWNED_FIELD_STRUCT_TYPE_BASE = 1_000_000
_OWNED_PAYLOAD_ENUM_TYPE_BASE = 1_100_000
_COPY_PAYLOAD_ENUM_TYPE_BASE = 1_000
_I64_STRUCT_TYPE_BASE = 2_000
_DESTRUCTOR_I64_STRUCT_TYPE_BASE = 3_000
_LEGACY_OWNED_PAYLOAD_ENUM_TYPE_BASE = 4_000
_SECTION_WIDTHS_BY_VERSION = {
    1: (16, 12, 5, 8, 4, 8, 7, 3, 1),
    2: (16, 12, 5, 8, 4, 8, 7, 3, 1, 5),
}


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
    )


def _descriptor_type_names(rows: tuple[tuple[int, ...], ...]) -> dict[int, MirType]:
    raw: dict[int, tuple[int, int, int, int]] = {}
    for index, row in enumerate(rows):
        code, kind, identity, child_code, destructor_policy = row
        if code <= 0 or identity < 0 or child_code <= 0 or kind not in {
            _TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT,
            _TYPE_DESCRIPTOR_OWNED_PAYLOAD_ENUM,
        }:
            raise ResolvedSourceFunctionSnapshotError(f"type descriptor {index} is invalid")
        if destructor_policy != 0:
            raise ResolvedSourceFunctionSnapshotError(
                f"type descriptor {index} has unsupported destructor policy"
            )
        if code in raw:
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

    resolved: dict[int, MirType] = {
        1: MirType("i64"),
        2: MirType("bool"),
    }

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
        if descriptor is None:
            raise ResolvedSourceFunctionSnapshotError(
                f"type descriptor references unresolved child code {code}"
            )
        if code in active:
            raise ResolvedSourceFunctionSnapshotError("type descriptor graph is cyclic")
        kind, identity, child_code, _ = descriptor
        child = resolve(child_code, active | {code})
        name = (
            "struct_owned_field"
            if kind == _TYPE_DESCRIPTOR_OWNED_FIELD_STRUCT
            else "enum_owned_payload"
        )
        result = MirType(f"{name}_{identity}", (child,))
        resolved[code] = result
        return result

    for code in raw:
        resolve(code, frozenset())
    return {code: resolved[code] for code in raw}


def materialize_resolved_source_function_snapshot(
    *,
    source: str,
    module_name: str,
    snapshot: ResolvedSourceFunctionSnapshot,
    capability_names: Mapping[int, str],
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    """Materialize a decoded native snapshot as canonical bootstrap-mir-v1."""

    descriptor_names = _descriptor_type_names(snapshot.type_descriptors)
    if type_names:
        for code, type_ in type_names.items():
            if code in descriptor_names and descriptor_names[code] != type_:
                raise ResolvedSourceFunctionSnapshotError(
                    f"type name for code {code} conflicts with native descriptor"
                )
        descriptor_names.update(type_names)
    return lower_native_ownership_whole_function_assembly(
        source=source,
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
