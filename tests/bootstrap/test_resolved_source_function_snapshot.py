from __future__ import annotations

import pytest

from merit.bootstrap.resolved_source_function_snapshot import (
    SNAPSHOT_MAGIC,
    SNAPSHOT_VERSION,
    ResolvedSourceFunctionSnapshotError,
    _descriptor_type_names,
    decode_resolved_source_function_snapshot,
)


def _v4_snapshot(
    *,
    destructors: tuple[tuple[int, ...], ...] = (),
    body: tuple[tuple[int, ...], ...] = (),
    cfg: tuple[tuple[int, ...], ...] = (),
    placements: tuple[tuple[int, ...], ...] = (),
) -> tuple[int, ...]:
    sections = ((),) * 10 + (destructors, body, cfg, placements)
    return (
        SNAPSHOT_MAGIC,
        SNAPSHOT_VERSION,
        *(value for section in sections for value in (len(section), *(item for row in section for item in row))),
    )


@pytest.mark.parametrize(
    ("values", "message"),
    (
        (_v4_snapshot(destructors=((3_000, -1, 0, 0, 0, 0, 0),)), "invalid"),
        (_v4_snapshot(destructors=((3_000, 1, 0, 0, 0, 0, 0),)), "noncanonical"),
        (_v4_snapshot(destructors=((3_000, 0, 1, 0, 0, 0, 0),)), "exceeds"),
        (
            _v4_snapshot(
                destructors=((3_000, 0, 0, 0, 0, 0, 0), (3_000, 0, 0, 0, 0, 0, 0))
            ),
            "duplicates target",
        ),
        (_v4_snapshot(body=((1,) * 16,)), "unreferenced"),
    ),
)
def test_v4_destructor_sections_fail_closed(values: tuple[int, ...], message: str) -> None:
    with pytest.raises(ResolvedSourceFunctionSnapshotError, match=message):
        decode_resolved_source_function_snapshot(values)


def test_native_type_descriptors_resolve_recursive_owned_aggregate_graph() -> None:
    names = _descriptor_type_names(
        (
            (1_000_001, 1, 1, 3_000, 0),
            (1_000_002, 1, 2, 1_000_001, 0),
            (1_100_000, 2, 0, 1_000_002, 0),
        )
    )

    assert names[1_000_002].name == "struct_owned_field_2"
    assert names[1_000_002].arguments[0].name == "struct_owned_field_1"
    assert names[1_100_000].arguments[0] == names[1_000_002]


def test_v3_native_type_descriptors_resolve_ordered_multi_field_aggregate() -> None:
    names = _descriptor_type_names(
        (
            (1_200_000, 3, 0, 1, 0),
            (1_200_000, 3, 0, 1, 1),
            (1_200_001, 3, 1, 1_200_000, 0),
            (1_200_001, 3, 1, 1, 0),
        ),
        version=3,
    )

    assert names[1_200_000].name == "struct_aggregate_0_destructor_1"
    assert [field.name for field in names[1_200_000].arguments] == ["i64", "i64"]
    assert names[1_200_001].arguments[0] == names[1_200_000]


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (((1_200_000, 3, 0, 1, 1), (1_200_000, 3, 0, 1, 1)), "duplicate destructor"),
        (((1_200_001, 3, 0, 1, 0), (1_200_001, 3, 0, 1, 0)), "noncanonical"),
        (((1_200_000, 3, 0, 1_200_000, 0), (1_200_000, 3, 0, 1, 0)), "cyclic"),
        (((1_200_000, 3, 0, 1, 2), (1_200_000, 3, 0, 1, 0)), "unsupported destructor"),
    ),
)
def test_v3_native_multi_field_type_descriptors_fail_closed(
    rows: tuple[tuple[int, ...], ...], message: str
) -> None:
    with pytest.raises(ResolvedSourceFunctionSnapshotError, match=message):
        _descriptor_type_names(rows, version=3)


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (((1_000_001, 1, 1, 3_000, 0), (1_000_001, 1, 1, 3_000, 0)), "duplicate"),
        (((1_000_001, 1, 1, 1_000_001, 0),), "cyclic"),
        (((1_000_001, 1, 1, 1_000_002, 0),), "unresolved"),
        (((1_000_002, 1, 1, 3_000, 0),), "noncanonical"),
        (((1_100_001, 2, 0, 3_000, 0),), "noncanonical"),
        (((1_000_001, 3, 1, 3_000, 0),), "invalid"),
        (((1_000_001, 1, 1, 3_000, 1),), "unsupported destructor policy"),
    ),
)
def test_native_type_descriptors_fail_closed(
    rows: tuple[tuple[int, ...], ...], message: str
) -> None:
    with pytest.raises(ResolvedSourceFunctionSnapshotError, match=message):
        _descriptor_type_names(rows)
