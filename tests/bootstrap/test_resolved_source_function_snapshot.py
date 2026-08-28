from __future__ import annotations

import pytest

from merit.bootstrap.resolved_source_function_snapshot import (
    ResolvedSourceFunctionSnapshotError,
    _descriptor_type_names,
)


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
