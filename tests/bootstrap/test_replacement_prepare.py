from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from merit.bootstrap.resolved_source_function_snapshot import SNAPSHOT_MAGIC, SNAPSHOT_VERSION
from merit.project.cli import main
from merit.project.loader import load_project
from merit.project.replacement import REPLACEMENT_MANIFEST, ReplacementProjectError, load_replacement_inputs
from merit.project.replacement_prepare import prepare_replacement_artifacts


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "prepare_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "prepare_project"\nentry = "src/main.mrt"\nsources = ["src/**/*.mrt"]\n\n[build]\nc_flags = ["-O2"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(
        "module main\nfn compute()->i64 { return 7; }\n",
        encoding="utf-8",
    )
    return root


def _producer(tmp_path: Path, *, exit_code: int = 0) -> Path:
    values = [SNAPSHOT_MAGIC, SNAPSHOT_VERSION] + [0] * 9
    path = tmp_path / "producer.py"
    path.write_text(
        "import os, sys\n"
        "source = sys.stdin.read()\n"
        "assert os.environ['MERIT_REPLACEMENT_PROTOCOL'] == 'resolved-source-function-snapshot-v1'\n"
        "assert os.environ['MERIT_REPLACEMENT_MODULE'] == 'main'\n"
        "assert 'fn compute' in source\n"
        + (f"sys.exit({exit_code})\n" if exit_code else "")
        + f"print({repr(chr(10).join(str(value) for value in values))})\n",
        encoding="utf-8",
    )
    return path


def test_prepare_replacement_publishes_native_snapshot_and_manifest(tmp_path: Path) -> None:
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    producer = _producer(tmp_path)

    prepared = prepare_replacement_artifacts(project, [sys.executable, str(producer)])

    assert prepared.manifest_path == root / ".merit" / REPLACEMENT_MANIFEST
    payload = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
    assert payload["producer_protocol"] == "resolved-source-function-snapshot-v1"
    assert payload["functions"][0]["module"] == "main"
    assert len(payload["functions"][0]["source_sha256"]) == 64
    inputs = load_replacement_inputs(project)
    assert len(inputs) == 1
    assert inputs[0].module_name == "main"
    assert inputs[0].snapshot_values[:2] == (SNAPSHOT_MAGIC, SNAPSHOT_VERSION)


def test_prepared_artifacts_are_rejected_after_source_changes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    producer = _producer(tmp_path)
    project = load_project(root / "Merit.toml")
    prepare_replacement_artifacts(project, [sys.executable, str(producer)])

    source_path = root / "src" / "main.mrt"
    source_path.write_text(
        "module main\nfn compute()->i64 { return 8; }\n",
        encoding="utf-8",
    )
    changed = load_project(root / "Merit.toml")
    with pytest.raises(ReplacementProjectError, match="stale after source changes"):
        load_replacement_inputs(changed)


def test_failed_native_producer_does_not_publish_manifest(tmp_path: Path) -> None:
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    producer = _producer(tmp_path, exit_code=9)

    with pytest.raises(ReplacementProjectError, match="exit code 9"):
        prepare_replacement_artifacts(project, [sys.executable, str(producer)])
    assert not (root / ".merit" / REPLACEMENT_MANIFEST).exists()


def test_prepare_replacement_cli_invokes_producer_and_reports_manifest(tmp_path: Path, capsys) -> None:
    root = _project(tmp_path)
    producer = _producer(tmp_path)

    status = main(
        [
            "prepare-replacement",
            str(root),
            "--replacement-producer",
            sys.executable,
            str(producer),
        ]
    )
    assert status == 0
    output = capsys.readouterr().out.strip()
    assert output.endswith(f".merit/{REPLACEMENT_MANIFEST}") or output.endswith(f".merit\\{REPLACEMENT_MANIFEST}")
