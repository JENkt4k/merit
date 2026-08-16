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
SNAPSHOT_VERSION = 1
_SECTION_WIDTHS = (16, 12, 5, 8, 4, 8, 7, 3, 1)


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


def decode_resolved_source_function_snapshot(values: Iterable[int]) -> ResolvedSourceFunctionSnapshot:
    data = tuple(int(value) for value in values)
    if len(data) < 2 or data[0] != SNAPSHOT_MAGIC:
        raise ResolvedSourceFunctionSnapshotError("resolved source snapshot has invalid magic")
    if data[1] != SNAPSHOT_VERSION:
        raise ResolvedSourceFunctionSnapshotError(
            f"unsupported resolved source snapshot version {data[1]}"
        )

    position = 2
    sections: list[tuple[tuple[int, ...], ...]] = []
    for section_index, width in enumerate(_SECTION_WIDTHS):
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
    )


def materialize_resolved_source_function_snapshot(
    *,
    source: str,
    module_name: str,
    snapshot: ResolvedSourceFunctionSnapshot,
    capability_names: Mapping[int, str],
    type_names: Mapping[int, MirType] | None = None,
) -> MirModule:
    """Materialize a decoded native snapshot as canonical bootstrap-mir-v1."""

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
        type_names=type_names,
    )
