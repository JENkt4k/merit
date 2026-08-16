from __future__ import annotations

import pytest

from merit.bootstrap.replacement_build import ReplacementBuildError
from merit.bootstrap.replacement_project import (
    ReplacementFunctionInput,
    build_replacement_project_artifact,
)


def test_replacement_project_rejects_empty_input():
    with pytest.raises(ReplacementBuildError, match="no resolved functions"):
        build_replacement_project_artifact((), module_name="demo")


def test_replacement_function_input_materializes_snapshot_values_once():
    values = (1, 2, 3)
    item = ReplacementFunctionInput.from_values(
        source="module demo\n",
        module_name="demo",
        snapshot_values=(value for value in values),
        capability_names={9: "clock"},
    )
    assert item.snapshot_values == values
    assert item.capability_names == {9: "clock"}
