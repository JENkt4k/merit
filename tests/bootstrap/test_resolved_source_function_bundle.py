from __future__ import annotations

import pytest

from merit.bootstrap.resolved_source_function_bundle import (
    BUNDLE_MAGIC,
    BUNDLE_VERSION,
    PROJECT_ARTIFACT_BUNDLE_VERSION,
    ResolvedSourceFunctionBundleError,
    decode_native_project_artifact_transport,
    decode_resolved_source_function_bundle,
    encode_resolved_source_function_bundle,
)
from merit.bootstrap.resolved_source_function_snapshot import (
    SNAPSHOT_MAGIC,
    SNAPSHOT_SECTION_COUNT,
    SNAPSHOT_VERSION,
)


def _snapshot(source: tuple[int, ...] = ()) -> tuple[int, ...]:
    return (
        SNAPSHOT_MAGIC,
        SNAPSHOT_VERSION,
        *([0] * (SNAPSHOT_SECTION_COUNT - 1)),
        len(source),
        *source,
    )


def test_bundle_round_trips_multiple_nested_snapshots() -> None:
    first = _snapshot()
    second = _snapshot()
    encoded = encode_resolved_source_function_bundle((first, second))
    assert encoded[:3] == (BUNDLE_MAGIC, BUNDLE_VERSION, 2)
    decoded = decode_resolved_source_function_bundle(encoded)
    assert decoded.encoded_snapshots == (first, second)
    assert len(decoded.functions) == 2


def test_bundle_v2_deduplicates_and_rehydrates_effective_source() -> None:
    source = tuple("module main".encode())
    snapshot = _snapshot(source)
    compact_snapshot = _snapshot()

    encoded = encode_resolved_source_function_bundle((snapshot, snapshot))

    metadata_length = 1 + 1 + len("main") + 1
    assert len(encoded) == 3 + 1 + len(snapshot) + 1 + len(_snapshot()) + metadata_length
    decoded = decode_resolved_source_function_bundle(encoded)
    assert decoded.encoded_snapshots == (snapshot, compact_snapshot)
    assert decoded.functions[0].effective_source_bytes == source
    assert decoded.functions[1].effective_source_bytes == source


def test_bundle_v1_remains_decodable() -> None:
    snapshot = _snapshot(tuple("old".encode()))
    encoded = (BUNDLE_MAGIC, 1, 1, len(snapshot), *snapshot)

    decoded = decode_resolved_source_function_bundle(encoded)

    assert decoded.encoded_snapshots == (snapshot,)


def test_bundle_v4_round_trips_native_project_artifacts() -> None:
    encoded = encode_resolved_source_function_bundle(
        (_snapshot(tuple(b"module main")),),
        module_name="demo",
        capability_names=("allocate",),
        canonical_mir=b"mir-v1\n",
        c_source=b"#include <stdint.h>\n",
        c_header=b"#pragma once\n",
    )

    assert encoded[:3] == (BUNDLE_MAGIC, PROJECT_ARTIFACT_BUNDLE_VERSION, 1)
    decoded = decode_resolved_source_function_bundle(encoded)
    assert decoded.module_name == "demo"
    assert decoded.capability_names == ("allocate",)
    assert decoded.canonical_mir_bytes == b"mir-v1\n"
    assert decoded.c_source_bytes == b"#include <stdint.h>\n"
    assert decoded.c_header_bytes == b"#pragma once\n"
    transport = decode_native_project_artifact_transport(encoded)
    assert transport.module_name == decoded.module_name
    assert transport.canonical_mir_bytes == decoded.canonical_mir_bytes


def test_v4_transport_treats_nested_snapshot_as_opaque() -> None:
    encoded = encode_resolved_source_function_bundle(
        (_snapshot(),), canonical_mir=b"mir", c_source=b"c", c_header=b"h"
    )
    snapshot_length = encoded[3]
    opaque = (*encoded[:3], 1, 0, *encoded[4 + snapshot_length:])

    transport = decode_native_project_artifact_transport(opaque)

    assert transport.canonical_mir_bytes == b"mir"
    with pytest.raises(ResolvedSourceFunctionBundleError, match="invalid"):
        decode_resolved_source_function_bundle(opaque)


@pytest.mark.parametrize("damage", ("truncated", "trailing", "bad-byte", "bad-metadata"))
def test_v4_transport_rejects_invalid_framing(damage: str) -> None:
    encoded = encode_resolved_source_function_bundle(
        (_snapshot(),), canonical_mir=b"mir", c_source=b"c", c_header=b"h"
    )
    if damage == "truncated":
        broken = encoded[:-1]
    elif damage == "trailing":
        broken = (*encoded, 0)
    elif damage == "bad-byte":
        broken = (*encoded[:-1], 256)
    else:
        metadata_index = 4 + encoded[3]
        broken = (*encoded[:metadata_index], 0, *encoded[metadata_index + 1:])
    with pytest.raises(ResolvedSourceFunctionBundleError):
        decode_native_project_artifact_transport(broken)


def test_bundle_v4_requires_all_nonempty_native_project_artifacts() -> None:
    with pytest.raises(ResolvedSourceFunctionBundleError, match="requires non-empty"):
        encode_resolved_source_function_bundle(
            (_snapshot(),), canonical_mir=b"mir", c_source=b"c"
        )


def test_bundle_v4_rejects_truncated_native_project_artifact() -> None:
    encoded = encode_resolved_source_function_bundle(
        (_snapshot(),), canonical_mir=b"mir", c_source=b"c", c_header=b"h"
    )
    with pytest.raises(ResolvedSourceFunctionBundleError, match="truncated C header"):
        decode_resolved_source_function_bundle(encoded[:-1])


def test_bundle_rejects_empty_function_set() -> None:
    with pytest.raises(ResolvedSourceFunctionBundleError, match="empty"):
        encode_resolved_source_function_bundle(())


def test_bundle_rejects_truncated_nested_snapshot() -> None:
    encoded = (BUNDLE_MAGIC, BUNDLE_VERSION, 1, len(_snapshot()), *_snapshot()[:-1])
    with pytest.raises(ResolvedSourceFunctionBundleError, match="truncated"):
        decode_resolved_source_function_bundle(encoded)


def test_bundle_rejects_trailing_data() -> None:
    encoded = (*encode_resolved_source_function_bundle((_snapshot(),)), 99)
    with pytest.raises(ResolvedSourceFunctionBundleError, match="trailing"):
        decode_resolved_source_function_bundle(encoded)


def test_bundle_rejects_invalid_nested_snapshot() -> None:
    invalid = (0, SNAPSHOT_VERSION, *([0] * SNAPSHOT_SECTION_COUNT))
    with pytest.raises(ResolvedSourceFunctionBundleError, match="snapshot 0 is invalid"):
        encode_resolved_source_function_bundle((invalid,))
