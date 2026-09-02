"""Versioned transport for multiple native resolved source-function snapshots.

A bundle groups one or more already-resolved function snapshots emitted for a
single Merit source unit.  Framing is intentionally simple and deterministic:

    magic, version, function_count,
    snapshot_value_count, <snapshot values>, ...

Each nested snapshot retains its own versioned resolved-source snapshot contract and
is decoded by the existing strict decoder.  This layer performs no source or
semantic reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from merit.bootstrap.resolved_source_function_snapshot import (
    ResolvedSourceFunctionSnapshot,
    decode_resolved_source_function_snapshot,
)

BUNDLE_MAGIC = 0x4D524246  # "MRBF"
BUNDLE_VERSION = 1


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
    values: list[int] = [BUNDLE_MAGIC, BUNDLE_VERSION, len(encoded)]
    for index, snapshot in enumerate(encoded):
        if not snapshot:
            raise ResolvedSourceFunctionBundleError(f"bundle snapshot {index} is empty")
        try:
            decode_resolved_source_function_snapshot(snapshot)
        except ValueError as exc:
            raise ResolvedSourceFunctionBundleError(
                f"bundle snapshot {index} is invalid: {exc}"
            ) from exc
        values.append(len(snapshot))
        values.extend(snapshot)
    return tuple(values)


def decode_resolved_source_function_bundle(
    values: Iterable[int],
) -> ResolvedSourceFunctionBundle:
    data = tuple(int(value) for value in values)
    if len(data) < 3 or data[0] != BUNDLE_MAGIC:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has invalid magic")
    if data[1] != BUNDLE_VERSION:
        raise ResolvedSourceFunctionBundleError(
            f"unsupported resolved source function bundle version {data[1]}"
        )
    count = data[2]
    if count <= 0:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has no functions")

    position = 3
    decoded: list[ResolvedSourceFunctionSnapshot] = []
    encoded: list[tuple[int, ...]] = []
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
        encoded.append(snapshot_values)
        decoded.append(snapshot)
        position = end

    if position != len(data):
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has trailing data")
    return ResolvedSourceFunctionBundle(tuple(decoded), tuple(encoded))
