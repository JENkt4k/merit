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
BUNDLE_VERSION = 3
PROJECT_ARTIFACT_BUNDLE_VERSION = 4
_SUPPORTED_BUNDLE_VERSIONS = frozenset({1, 2, BUNDLE_VERSION, PROJECT_ARTIFACT_BUNDLE_VERSION})
_METADATA_MAGIC = 0x4D455441  # "META"
_PROJECT_ARTIFACT_MAGIC = 0x4D434152  # "MCAR"
_BUNDLE_MAGIC_INDEX = 0
_BUNDLE_VERSION_INDEX = 1
_BUNDLE_FUNCTION_COUNT_INDEX = 2
_BUNDLE_HEADER_WIDTH = 3


class ResolvedSourceFunctionBundleError(ValueError):
    """Raised when a native resolved-function bundle is malformed."""


@dataclass(frozen=True)
class ResolvedSourceFunctionBundle:
    functions: tuple[ResolvedSourceFunctionSnapshot, ...]
    encoded_snapshots: tuple[tuple[int, ...], ...]
    module_name: str = ""
    capability_names: tuple[str, ...] = ()
    canonical_mir_bytes: bytes = b""
    c_source_bytes: bytes = b""
    c_header_bytes: bytes = b""


def encode_resolved_source_function_bundle(
    snapshots: Iterable[Iterable[int]],
    *,
    module_name: str = "main",
    capability_names: Iterable[str] = (),
    canonical_mir: bytes | None = None,
    c_source: bytes | None = None,
    c_header: bytes | None = None,
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
    artifact_fields = (canonical_mir, c_source, c_header)
    carries_artifacts = any(value is not None for value in artifact_fields)
    if carries_artifacts and any(not value for value in artifact_fields):
        raise ResolvedSourceFunctionBundleError(
            "project artifact bundle requires non-empty canonical MIR, C source, and C header"
        )
    version = PROJECT_ARTIFACT_BUNDLE_VERSION if carries_artifacts else BUNDLE_VERSION
    values: list[int] = [BUNDLE_MAGIC, version, len(encoded)]
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
    module_bytes = module_name.encode("utf-8")
    encoded_capabilities = tuple(name.encode("utf-8") for name in capability_names)
    values.extend((_METADATA_MAGIC, len(module_bytes), *module_bytes, len(encoded_capabilities)))
    for name in encoded_capabilities:
        values.extend((len(name), *name))
    if carries_artifacts:
        values.append(_PROJECT_ARTIFACT_MAGIC)
        for field in artifact_fields:
            payload = bytes(field or b"")
            values.extend((len(payload), *payload))
    return tuple(values)


def decode_resolved_source_function_bundle(
    values: Iterable[int],
) -> ResolvedSourceFunctionBundle:
    data = tuple(int(value) for value in values)
    if len(data) < _BUNDLE_HEADER_WIDTH or data[_BUNDLE_MAGIC_INDEX] != BUNDLE_MAGIC:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has invalid magic")
    bundle_version = data[_BUNDLE_VERSION_INDEX]
    if bundle_version not in _SUPPORTED_BUNDLE_VERSIONS:
        raise ResolvedSourceFunctionBundleError(
            f"unsupported resolved source function bundle version {bundle_version}"
        )
    count = data[_BUNDLE_FUNCTION_COUNT_INDEX]
    if count <= 0:
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has no functions")

    position = _BUNDLE_HEADER_WIDTH
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
        encoded_snapshot_values = snapshot_values
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
        # Preserve the compact transport representation.  ``functions`` holds
        # the hydrated snapshots used by in-memory consumers, while prepared
        # artifacts can continue to share the canonical source supplied by the
        # project unit instead of duplicating it into every snapshot file.
        encoded.append(encoded_snapshot_values)
        decoded.append(snapshot)
        position = end

    module_name = ""
    capability_names: tuple[str, ...] = ()
    canonical_mir_bytes = b""
    c_source_bytes = b""
    c_header_bytes = b""
    if bundle_version >= 3:
        if position >= len(data) or data[position] != _METADATA_MAGIC:
            raise ResolvedSourceFunctionBundleError("resolved source function bundle is missing metadata")
        position += 1
        try:
            module_length = data[position]
            position += 1
            module_end = position + module_length
            module_name = bytes(data[position:module_end]).decode("utf-8")
            position = module_end
            capability_count = data[position]
            position += 1
            names: list[str] = []
            for _ in range(capability_count):
                name_length = data[position]
                position += 1
                name_end = position + name_length
                names.append(bytes(data[position:name_end]).decode("utf-8"))
                position = name_end
            capability_names = tuple(names)
        except (IndexError, UnicodeDecodeError, ValueError) as exc:
            raise ResolvedSourceFunctionBundleError(
                "resolved source function bundle has invalid metadata"
            ) from exc
        if not module_name:
            raise ResolvedSourceFunctionBundleError(
                "resolved source function bundle metadata has no module name"
            )
    if bundle_version >= PROJECT_ARTIFACT_BUNDLE_VERSION:
        if position >= len(data) or data[position] != _PROJECT_ARTIFACT_MAGIC:
            raise ResolvedSourceFunctionBundleError(
                "resolved source function bundle is missing project artifacts"
            )
        position += 1
        artifacts: list[bytes] = []
        try:
            for label in ("canonical MIR", "C source", "C header"):
                length = data[position]
                position += 1
                if length <= 0:
                    raise ResolvedSourceFunctionBundleError(
                        f"resolved source function bundle has empty {label}"
                    )
                end = position + length
                if end > len(data):
                    raise ResolvedSourceFunctionBundleError(
                        f"resolved source function bundle has truncated {label}"
                    )
                payload = data[position:end]
                if any(value < 0 or value > 255 for value in payload):
                    raise ResolvedSourceFunctionBundleError(
                        f"resolved source function bundle has invalid {label} byte"
                    )
                artifacts.append(bytes(payload))
                position = end
        except IndexError as exc:
            raise ResolvedSourceFunctionBundleError(
                "resolved source function bundle has truncated project artifacts"
            ) from exc
        canonical_mir_bytes, c_source_bytes, c_header_bytes = artifacts
    if position != len(data):
        raise ResolvedSourceFunctionBundleError("resolved source function bundle has trailing data")
    return ResolvedSourceFunctionBundle(
        tuple(decoded), tuple(encoded), module_name, capability_names,
        canonical_mir_bytes, c_source_bytes, c_header_bytes,
    )
