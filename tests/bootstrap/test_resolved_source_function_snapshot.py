from __future__ import annotations

import pytest

from merit.bootstrap.resolved_source_function_snapshot import (
    SNAPSHOT_MAGIC,
    ResolvedSourceFunctionSnapshotError,
    _descriptor_type_names,
    _numeric_descriptor_type_names,
    decode_resolved_source_function_snapshot,
)


LEGACY_DESTRUCTOR_SNAPSHOT_VERSION = 4


def test_v6_numeric_descriptors_preserve_decimal_and_full_u64_bounded_domains() -> None:
    names = _numeric_descriptor_type_names(
        (
            (1_300_000, 1, 0, 0, 0, 18, 2, 0, 0, 0, 0),
            (1_400_000, 2, 0, 11, 1, 0, 1, 1, 9_999_999_999, 999_999_999, 0),
        )
    )

    assert names[1_300_000].name == "decimal_0_18_2_0"
    assert names[1_400_000].name == "bounded_0_11_1_9999999999999999999"
    assert names[1_400_000].arguments == (names[1_400_000].arguments[0],)
    assert names[1_400_000].arguments[0].name == "u64"


@pytest.mark.parametrize(
    ("row", "message"),
    (
        ((1_300_000, 1, 0, 0, 0, 18, 2, 1, 0, 0, 0), "noncanonical"),
        ((1_400_000, 2, 0, 11, 1, 0, 0, 0, 0, 0, 0), "invalid range"),
        ((1_400_000, 2, 0, 11, 1, 0, 1_000_000_000, 1, 0, 2, 0), "invalid range"),
        ((1_400_000, 2, 0, 11, 1, 0, 3, 1, 0, 2, 0), "invalid range"),
    ),
)
def test_v6_numeric_descriptors_fail_closed(row: tuple[int, ...], message: str) -> None:
    with pytest.raises(ResolvedSourceFunctionSnapshotError, match=message):
        _numeric_descriptor_type_names((row,))


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
        LEGACY_DESTRUCTOR_SNAPSHOT_VERSION,
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


def test_v5_native_type_descriptors_resolve_ordered_heterogeneous_enum() -> None:
    names = _descriptor_type_names(
        (
            (1_100_000, 2, 0, 3_000, 0, 0),
            (1_100_000, 2, 0, 1, 0, 1),
        ),
        version=5,
    )

    assert names[1_100_000].name == "enum_owned_payload_0"
    assert [payload.name for payload in names[1_100_000].arguments] == [
        "struct_i64_destructor_0", "i64"
    ]


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (((1_100_000, 2, 0, 3_000, 0, 1),), "variant ordinal"),
        (
            ((1_100_000, 2, 0, 3_000, 0, 0), (1_100_000, 2, 0, 1, 0, 0)),
            "variant ordinal",
        ),
        (((1_100_001, 2, 0, 3_000, 0, 0),), "noncanonical"),
        (((1_100_000, 2, 0, 3_000, 1, 0),), "destructor policy"),
    ),
)
def test_v5_native_heterogeneous_enum_descriptors_fail_closed(
    rows: tuple[tuple[int, ...], ...], message: str
) -> None:
    with pytest.raises(ResolvedSourceFunctionSnapshotError, match=message):
        _descriptor_type_names(rows, version=5)


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


def test_v9_native_type_descriptors_preserve_public_stable_abi_names() -> None:
    source = 'pub stable("point-v1") struct Point { x:i32; y:i32; }'
    names = _descriptor_type_names(
        (
            (1_200_000, 3, 0, 7, 0, 0, source.index("Point"), 5, source.index("x:"), 1, 3),
            (1_200_000, 3, 0, 7, 0, 1, source.index("Point"), 5, source.index("y:"), 1, 3),
        ),
        version=9,
        source=source,
    )

    assert names[1_200_000].name.endswith("__abi_3_506f696e74_78_79")
    assert [field.name for field in names[1_200_000].arguments] == ["i32", "i32"]


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
