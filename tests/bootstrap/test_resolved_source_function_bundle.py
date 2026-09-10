from __future__ import annotations

import pytest

from merit.bootstrap.resolved_source_function_bundle import (
    BUNDLE_MAGIC,
    BUNDLE_VERSION,
    ResolvedSourceFunctionBundleError,
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

    assert len(encoded) == 3 + 1 + len(snapshot) + 1 + len(_snapshot())
    decoded = decode_resolved_source_function_bundle(encoded)
    assert decoded.encoded_snapshots == (snapshot, compact_snapshot)
    assert decoded.functions[0].effective_source_bytes == source
    assert decoded.functions[1].effective_source_bytes == source


def test_bundle_v1_remains_decodable() -> None:
    snapshot = _snapshot(tuple("old".encode()))
    encoded = (BUNDLE_MAGIC, 1, 1, len(snapshot), *snapshot)

    decoded = decode_resolved_source_function_bundle(encoded)

    assert decoded.encoded_snapshots == (snapshot,)


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
