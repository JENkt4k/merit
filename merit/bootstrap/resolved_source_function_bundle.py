"""Versioned transport for multiple native resolved source-function snapshots.

A bundle groups one or more already-resolved function snapshots emitted for a
single Merit source unit.  Framing is intentionally simple and deterministic:

    magic, version, function_count,
    snapshot_value_count, <snapshot values>, ...

Bundle v2 carries the canonical effective source in the first nested snapshot;
later snapshots may encode an empty final source section and inherit that byte
sequence. Each materialized nested snapshot still retains the complete existing
resolved-source snapshot contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from merit.bootstrap.resolved_source_function_snapshot import (
    ResolvedSourceFunctionSnapshot,
    decode_resolved_source_function_snapshot,
)

BUNDLE_MAGIC = 0x4D524246  # "MRBF"
BUNDLE_VERSION = 2
_SUPPORTED_BUNDLE_VERSIONS = frozenset({1, BUNDLE_VERSION})


class ResolvedSourceFunctionBundleError(ValueError):
    """Raised when a native resolved-function bundle is malformed."""


@dataclass(frozen=True)
class ResolvedSourceFunctionBundle:
    functions: tuple[ResolvedSourceFunctionSnapshot, ...]
    encoded_snapshots: tuple[tuple[int, ...], ...]


def encode_resolved_source_function_bundle(
    snapshots: Iterable[Iterable[int]],
) -> tuple[int, ...]:
    """Frame already-encoded snapshots after validating every nested payload."""

    encoded = tuple(tuple(int(value) for value in snapshot) for snapshot in snapshots)
    if not encoded:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle is empty")
    decoded_snapshots: list[ResolvedSourceFunctionSnapshot] = []
    for index, snapshot in enumerate(encoded):
        if not snapshot:
            raise ResolvedSourceFunctionBundleError(f"bundle snapshot {index} is empty")
        try:
            decoded_snapshots.append(decode_resolved_source_function_snapshot(snapshot))
        except ValueError as exc:
            raise ResolvedSourceFunctionBundleError(
                f"bundle snapshot {index} is invalid: {exc}"
            ) from exc

    shared_source = decoded_snapshots[0].effective_source_bytes
    values: list[int] = [BUNDLE_MAGIC, BUNDLE_VERSION, len(encoded)]
    for index, snapshot in enumerate(encoded):
        source = decoded_snapshots[index].effective_source_bytes
        if source != shared_source:
            raise ResolvedSourceFunctionBundleError(
                f"bundle snapshot {index} has a different effective source"
            )
        encoded_snapshot = snapshot
        if index > 0 and shared_source:
            encoded_snapshot = snapshot[: -len(shared_source) - 1] + (0,)
        values.append(len(encoded_snapshot))
        values.extend(encoded_snapshot)
    return tuple(values)


def decode_resolved_source_function_bundle(
    values: Iterable[int],
) -> ResolvedSourceFunctionBundle:
    data = tuple(int(value) for value in values)
    if len(data) < 3 or data[0] != BUNDLE_MAGIC:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has invalid magic")
    if data[1] not in _SUPPORTED_BUNDLE_VERSIONS:
        raise ResolvedSourceFunctionBundleError(
            f"unsupported resolved source function bundle version {data[1]}"
        )
    count = data[2]
    if count <= 0:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has no functions")

    bundle_version = data[1]
    position = 3
    decoded: list[ResolvedSourceFunctionSnapshot] = []
    encoded: list[tuple[int, ...]] = []
    shared_source: tuple[int, ...] = ()
    for index in range(count):
        if position >= len(data):
            raise ResolvedSourceFunctionBundleError(
                f"resolved source function bundle is missing length for function {index}"
            )
        length = data[position]
        position += 1
        if length <= 0:
            raise ResolvedSourceFunctionBundleError(
                f"resolved source function bundle function {index} has invalid length {length}"
            )
        end = position + length
        if end > len(data):
            raise ResolvedSourceFunctionBundleError(
                f"resolved source function bundle function {index} is truncated"
            )
        snapshot_values = tuple(data[position:end])
        try:
            snapshot = decode_resolved_source_function_snapshot(snapshot_values)
        except ValueError as exc:
            raise ResolvedSourceFunctionBundleError(
                f"resolved source function bundle function {index} is invalid: {exc}"
            ) from exc
        if bundle_version >= 2:
            source = snapshot.effective_source_bytes
            if index == 0:
                shared_source = source
            elif not source and shared_source:
                snapshot_values = snapshot_values[:-1] + (len(shared_source), *shared_source)
                snapshot = decode_resolved_source_function_snapshot(snapshot_values)
            elif source != shared_source:
                raise ResolvedSourceFunctionBundleError(
                    f"resolved source function bundle function {index} has a different effective source"
                )
        encoded.append(snapshot_values)
        decoded.append(snapshot)
        position = end

    if position != len(data):
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has trailing data")
    return ResolvedSourceFunctionBundle(tuple(decoded), tuple(encoded))
