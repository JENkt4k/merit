from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from merit.bootstrap.replacement_project import ReplacementFunctionInput
from merit.bootstrap.resolved_source_function_snapshot import (
    SNAPSHOT_MAGIC,
    SNAPSHOT_SECTION_COUNT,
    SNAPSHOT_VERSION,
)
from merit.project.cli import _replacement_driver_path, main
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
    status = main(["build", str(root)])
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
    values = [SNAPSHOT_MAGIC, SNAPSHOT_VERSION] + [0] * SNAPSHOT_SECTION_COUNT
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
    assert "Python reference/oracle command" in capsys.readouterr().err


def test_replacement_cli_routes_shared_build_without_reference_fallback(
    tmp_path: Path, capsys, monkeypatch,
) -> None:
    root = _project(tmp_path)
    library = root / "build" / "replacement_project.so"
    observed: list[tuple[object, Path]] = []

    def fake_build_shared(project, output: Path):
        observed.append((project, output))
        return SimpleNamespace(library=library)

    monkeypatch.setattr("merit.project.cli.build_replacement_shared", fake_build_shared)
    status = main(["build-shared", str(root)])

    assert status == 0
    assert observed and observed[0][1] == root / "build" / "replacement_project"
    assert capsys.readouterr().out.strip() == str(library)


def test_replacement_mode_is_explicit_in_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--compiler {reference,replacement}" in output
    assert "default: replacement" in " ".join(output.split())
    assert "Python oracle explicitly" in " ".join(output.split())


def test_default_build_prepares_with_configured_native_driver_without_reference_parser(
    tmp_path: Path, capsys, monkeypatch,
) -> None:
    root = _project(tmp_path)
    driver = tmp_path / "merit-replacement-frontend"
    driver.write_bytes(b"native driver placeholder")
    executable = root / "build" / "replacement_project"
    observed: list[str] = []

    def fail_reference_load(_path: Path):
        raise AssertionError("default production build invoked the Python reference loader")

    def fake_prepare(project, configured_driver):
        observed.append(f"prepare:{configured_driver.executable}")

    def fake_build(project, output: Path):
        observed.append(f"build:{output}")
        return SimpleNamespace(executable=executable)

    monkeypatch.setattr("merit.project.cli.load_project", fail_reference_load)
    monkeypatch.setattr("merit.project.cli.prepare_replacement_artifacts", fake_prepare)
    monkeypatch.setattr("merit.project.cli.build_replacement_project", fake_build)

    status = main(["build", str(root), "--replacement-driver", str(driver)])

    assert status == 0
    assert observed == [
        f"prepare:{driver}",
        f"build:{root / 'build' / 'replacement_project'}",
    ]
    assert capsys.readouterr().out.strip() == str(executable)


def test_replacement_driver_discovery_prefers_argument_then_environment_then_path(
    tmp_path: Path, monkeypatch,
) -> None:
    argument = tmp_path / "argument-driver"
    environment = tmp_path / "environment-driver"
    path_driver = tmp_path / "path-driver"
    monkeypatch.setenv("MERIT_REPLACEMENT_DRIVER", str(environment))
    monkeypatch.setattr("merit.project.cli.shutil.which", lambda _name: str(path_driver))

    assert _replacement_driver_path(str(argument)) == argument
    assert _replacement_driver_path(None) == environment

    monkeypatch.delenv("MERIT_REPLACEMENT_DRIVER")
    assert _replacement_driver_path(None) == path_driver


def test_default_check_runs_native_frontend_preparation(
    tmp_path: Path, capsys, monkeypatch,
) -> None:
    root = _project(tmp_path)
    driver = tmp_path / "replacement-driver"
    manifest = root / ".merit" / REPLACEMENT_MANIFEST
    observed: list[Path] = []

    def fake_prepare(_project, configured_driver):
        observed.append(configured_driver.executable)
        return SimpleNamespace(manifest_path=manifest)

    monkeypatch.setattr("merit.project.cli.prepare_replacement_artifacts", fake_prepare)
    assert main(["check", str(root), "--replacement-driver", str(driver)]) == 0
    assert observed == [driver]
    assert "native replacement frontend" in capsys.readouterr().out


def test_default_run_uses_replacement_executable(tmp_path: Path, monkeypatch) -> None:
    root = _project(tmp_path)
    executable = root / "build" / "replacement_project"
    observed: list[object] = []

    monkeypatch.setattr(
        "merit.project.cli.build_replacement_project",
        lambda _project, _output: SimpleNamespace(executable=executable),
    )

    def fake_run(command, **_kwargs):
        observed.append(command)
        return SimpleNamespace(returncode=23)

    monkeypatch.setattr("merit.project.cli.subprocess.run", fake_run)
    assert main(["run", str(root)]) == 23
    assert observed == [[str(executable)]]


@pytest.mark.parametrize("command", ("layout", "audit", "verify"))
def test_reference_oracle_commands_require_explicit_reference_selection(
    command: str, tmp_path: Path, capsys,
) -> None:
    root = _project(tmp_path)
    assert main([command, str(root)]) == 1
    assert "--compiler reference" in capsys.readouterr().err
