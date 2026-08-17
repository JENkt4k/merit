from __future__ import annotations

import json
from pathlib import Path

import pytest

from merit.bootstrap.replacement_project import ReplacementFunctionInput
from merit.bootstrap.resolved_source_function_snapshot import SNAPSHOT_MAGIC, SNAPSHOT_VERSION
from merit.project.cli import main
from merit.project.loader import load_project
from merit.project.replacement import REPLACEMENT_MANIFEST, REPLACEMENT_SCHEMA, load_replacement_inputs


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "replacement_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "replacement_project"\nentry = "src/main.mrt"\nsources = ["src/**/*.mrt"]\n\n[build]\nc_flags = ["-O2"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(
        "module main\nfn main()->i32 { return 0; }\n",
        encoding="utf-8",
    )
    return root


def test_replacement_cli_fails_closed_when_native_artifacts_are_missing(tmp_path: Path, capsys) -> None:
    root = _project(tmp_path)
    status = main(["build", str(root), "--compiler", "replacement"])
    assert status == 1
    error = capsys.readouterr().err
    assert "native frontend artifacts are missing" in error
    assert "refusing to fall back" in error
    assert not (root / "build" / "replacement_project").exists()


def test_replacement_manifest_loads_snapshot_transport_without_reference_semantics(tmp_path: Path) -> None:
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    artifact_dir = root / ".merit"
    artifact_dir.mkdir()
    # Structurally valid empty-section snapshot; semantic materialization is a
    # later boundary. This proves project loading transports native records
    # rather than deriving semantic records from Program.
    values = [SNAPSHOT_MAGIC, SNAPSHOT_VERSION] + [0] * 9
    (artifact_dir / "main.snapshot").write_text("\n".join(map(str, values)) + "\n", encoding="utf-8")
    (artifact_dir / REPLACEMENT_MANIFEST).write_text(
        json.dumps({
            "schema": REPLACEMENT_SCHEMA,
            "functions": [{"module": "main", "snapshot": "main.snapshot"}],
        }),
        encoding="utf-8",
    )
    inputs = load_replacement_inputs(project)
    assert len(inputs) == 1
    assert isinstance(inputs[0], ReplacementFunctionInput)
    assert inputs[0].module_name == "main"
    assert inputs[0].snapshot_values == tuple(values)


def test_replacement_cli_rejects_reference_only_commands(tmp_path: Path, capsys) -> None:
    root = _project(tmp_path)
    status = main(["verify", str(root), "--compiler", "replacement"])
    assert status == 1
    assert "does not support 'verify'" in capsys.readouterr().err


def test_replacement_mode_is_explicit_in_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--compiler {reference,replacement}" in output
    assert "never falls back" in output
