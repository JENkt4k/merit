from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from merit.bootstrap.resolved_source_function_bundle import (
    BUNDLE_MAGIC,
    BUNDLE_VERSION,
    encode_resolved_source_function_bundle,
)
from merit.bootstrap.resolved_source_function_snapshot import SNAPSHOT_MAGIC, SNAPSHOT_VERSION
from merit.project.cli import main
from merit.project.loader import load_project
from merit.project.replacement import REPLACEMENT_MANIFEST, ReplacementProjectError, load_replacement_inputs
from merit.project.replacement_prepare import PRODUCER_PROTOCOL, prepare_replacement_artifacts


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "prepare_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "prepare_project"\nentry = "src/main.mrt"\nsources = ["src/**/*.mrt"]\n\n[build]\nc_flags = ["-O2"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(
        "module main\nfn helper()->i64 { return 6; }\nfn main()->i32 { return 7; }\n",
        encoding="utf-8",
    )
    return root


def _producer(tmp_path: Path, *, exit_code: int = 0, function_count: int = 2) -> Path:
    snapshot = (SNAPSHOT_MAGIC, SNAPSHOT_VERSION, *([0] * 9))
    values = encode_resolved_source_function_bundle(snapshot for _ in range(function_count))
    path = tmp_path / "producer.py"
    path.write_text(
        "import os, sys\n"
        "source = sys.stdin.read()\n"
        f"assert os.environ['MERIT_REPLACEMENT_PROTOCOL'] == {PRODUCER_PROTOCOL!r}\n"
        "assert os.environ['MERIT_REPLACEMENT_MODULE'] == 'main'\n"
        "assert 'MERIT_REPLACEMENT_FUNCTION_INDEX' not in os.environ\n"
        "assert 'fn helper' in source and 'fn main' in source\n"
        + (f"sys.exit({exit_code})\n" if exit_code else "")
        + f"print({repr(chr(10).join(str(value) for value in values))})\n",
        encoding="utf-8",
    )
    return path


def test_prepare_replacement_publishes_every_native_function_and_manifest(tmp_path: Path) -> None:
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    producer = _producer(tmp_path)

    prepared = prepare_replacement_artifacts(project, [sys.executable, str(producer)])

    assert prepared.manifest_path == root / ".merit" / REPLACEMENT_MANIFEST
    assert len(prepared.snapshot_paths) == 2
    payload = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
    assert payload["producer_protocol"] == PRODUCER_PROTOCOL
    assert [item["module"] for item in payload["functions"]] == ["main", "main"]
    assert [item["function_index"] for item in payload["functions"]] == [0, 1]
    assert all(len(item["source_sha256"]) == 64 for item in payload["functions"])
    inputs = load_replacement_inputs(project)
    assert len(inputs) == 2
    assert [item.module_name for item in inputs] == ["main", "main"]
    assert all(item.snapshot_values[:2] == (SNAPSHOT_MAGIC, SNAPSHOT_VERSION) for item in inputs)


def test_prepared_artifacts_are_rejected_after_source_changes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    producer = _producer(tmp_path)
    project = load_project(root / "Merit.toml")
    prepare_replacement_artifacts(project, [sys.executable, str(producer)])

    source_path = root / "src" / "main.mrt"
    source_path.write_text(
        "module main\nfn helper()->i64 { return 6; }\nfn main()->i32 { return 8; }\n",
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


def test_prepare_replacement_rejects_unframed_single_snapshot(tmp_path: Path) -> None:
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    path = tmp_path / "legacy_producer.py"
    snapshot = [SNAPSHOT_MAGIC, SNAPSHOT_VERSION] + [0] * 9
    path.write_text(
        "import sys\nsys.stdin.read()\n"
        + f"print({repr(chr(10).join(str(value) for value in snapshot))})\n",
        encoding="utf-8",
    )
    with pytest.raises(ReplacementProjectError, match="invalid bundle"):
        prepare_replacement_artifacts(project, [sys.executable, str(path)])


def test_prepare_replacement_cli_invokes_bundle_producer_and_reports_manifest(tmp_path: Path, capsys) -> None:
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
