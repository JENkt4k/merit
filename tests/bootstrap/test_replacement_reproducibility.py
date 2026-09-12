from __future__ import annotations

from pathlib import Path

import pytest

from merit.bootstrap.native_frontend_driver import ReplacementCompilerStage
from merit.bootstrap.native_frontend_driver import _copy_isolated_compiler_source
from merit.bootstrap.reproducibility import ReproducibilityError, build_reproducibility_evidence
from merit.project.replacement_prepare import NativeReplacementDriver


def _driver(path: Path) -> NativeReplacementDriver:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"native-driver")
    return NativeReplacementDriver(path)


def _stage(path: Path, canonical: bytes) -> ReplacementCompilerStage:
    driver = _driver(path / "merit-frontend")
    c_path = path / "frontend.c"
    header_path = path / "frontend.h"
    library = path / "frontend.so"
    c_path.write_bytes(canonical)
    header_path.write_bytes(b"canonical header")
    library.write_bytes(b"platform library")
    return ReplacementCompilerStage(driver, c_path, header_path, library)


def test_reproducibility_evidence_compares_canonical_artifacts_and_protocol(
    tmp_path: Path, monkeypatch,
) -> None:
    stage0 = _driver(tmp_path / "stage-0-driver")
    stages = iter((_stage(tmp_path / "stage-1", b"canonical C"), _stage(tmp_path / "stage-2", b"canonical C")))
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_native_replacement_driver", lambda _path: stage0)
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_replacement_compiler_stage", lambda _path, _producer: next(stages))
    monkeypatch.setattr("merit.bootstrap.reproducibility._driver_output", lambda _driver: b"canonical protocol")

    progress = []
    evidence = build_reproducibility_evidence(
        tmp_path / "evidence",
        progress=lambda label, status, elapsed: progress.append((label, status, elapsed)),
    )

    assert evidence["status"] == "passed"
    assert evidence["isolated_source_staging"] is True
    assert evidence["stages"]["stage_1"]["generated_c_sha256"] == evidence["stages"]["stage_2"]["generated_c_sha256"]
    assert set(evidence["timings_seconds"]) == {
        "stage_0_build", "stage_1_build", "stage_2_build",
        "stage_0_probe", "stage_1_probe", "stage_2_probe",
    }
    assert progress[0][:2] == ("stage_0_build", "started")
    assert progress[-1][:2] == ("stage_2_probe", "passed")


def test_reproducibility_progress_reports_failed_stage(
    tmp_path: Path, monkeypatch,
) -> None:
    events = []
    monkeypatch.setattr(
        "merit.bootstrap.reproducibility.build_native_replacement_driver",
        lambda _path: (_ for _ in ()).throw(OSError("build failed")),
    )

    with pytest.raises(OSError, match="build failed"):
        build_reproducibility_evidence(
            tmp_path / "evidence",
            progress=lambda label, status, elapsed: events.append((label, status, elapsed)),
        )

    assert [event[:2] for event in events] == [
        ("stage_0_build", "started"),
        ("stage_0_build", "failed"),
    ]


def test_reproducibility_evidence_fails_when_next_stage_canonical_source_differs(
    tmp_path: Path, monkeypatch,
) -> None:
    stage0 = _driver(tmp_path / "stage-0-driver")
    stages = iter((_stage(tmp_path / "stage-1", b"first"), _stage(tmp_path / "stage-2", b"second")))
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_native_replacement_driver", lambda _path: stage0)
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_replacement_compiler_stage", lambda _path, _producer: next(stages))

    with pytest.raises(ReproducibilityError, match="canonical generated C/header artifacts differ"):
        build_reproducibility_evidence(tmp_path / "evidence")


def test_isolated_compiler_source_excludes_prior_build_state(
    tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    manifest = source / "Merit.toml"
    manifest.write_text("[package]\nname='compiler'\n", encoding="utf-8")
    for ignored in (".merit", "build", "__pycache__"):
        directory = source / ignored
        directory.mkdir()
        (directory / "residue").write_text("stale", encoding="utf-8")
    (source / "stale.pyc").write_bytes(b"stale")
    monkeypatch.setattr("merit.bootstrap.native_frontend_driver.BOOTSTRAP_PROJECT", manifest)

    destination = tmp_path / "isolated"
    _copy_isolated_compiler_source(destination)

    assert (destination / "Merit.toml").is_file()
    assert not (destination / ".merit").exists()
    assert not (destination / "build").exists()
    assert not (destination / "__pycache__").exists()
    assert not (destination / "stale.pyc").exists()
