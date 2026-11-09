from __future__ import annotations

from pathlib import Path

import pytest

from merit.bootstrap.native_frontend_driver import _copy_isolated_compiler_source
from merit.bootstrap.reproducibility import SCHEMA, ReproducibilityError, build_reproducibility_evidence
from merit.bootstrap.self_hosting import SelfHostingError, Stage


def _stages(root: Path) -> tuple[Stage, Stage, Stage]:
    return tuple(
        Stage(name, None if index == 0 else root / f"stage-{index-1}",
              root / f"{name}-source", root / name / "compiler",
              ("merit-project", "build", name), 1.0, {}, {}, "v4")
        for index, name in enumerate(("stage_0", "stage_1", "stage_2"))
    )


def _comparison() -> dict[str, object]:
    return {
        "canonical_artifact_sha256": {
            "c_source": "canonical-c", "c_header": "canonical-header",
            "canonical_mir": "canonical-mir",
        },
        "fixed_probes": {
            "accepted": {"stdout_sha256": "protocol", "request_sha256": "request"},
        },
    }


def test_reproducibility_evidence_compares_canonical_artifacts_and_protocol(
    tmp_path: Path, monkeypatch,
) -> None:
    stages = _stages(tmp_path)
    calls = []
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_stages",
                        lambda path: (calls.append(path), stages)[1])
    monkeypatch.setattr("merit.bootstrap.reproducibility.compare_stage_bytes",
                        lambda built: (calls.append(built), _comparison())[1])

    progress = []
    evidence = build_reproducibility_evidence(
        tmp_path / "evidence",
        progress=lambda label, status, elapsed: progress.append((label, status, elapsed)),
    )

    assert evidence["status"] == "passed"
    assert evidence["schema"] == SCHEMA
    assert evidence["supersedes"] == "merit-alpha2-reproducibility-v1"
    assert evidence["isolated_source_staging"] is True
    assert evidence["stages"]["stage_1"]["generated_c_sha256"] == evidence["stages"]["stage_2"]["generated_c_sha256"]
    assert evidence["stages"]["stage_1"]["public_command"][0] == "merit-project"
    assert evidence["probe_protocol_sha256"] == "protocol"
    assert evidence["probe_request_sha256"] == "request"
    assert set(evidence["timings_seconds"]) == {"public_stage_build", "canonical_comparison"}
    assert calls[0].name == "stages"
    assert calls[0].parent.parent == tmp_path / "evidence"
    assert calls[1] == stages
    assert progress[0][:2] == ("public_stage_build", "started")
    assert progress[-1][:2] == ("canonical_comparison", "passed")


def test_reproducibility_progress_reports_failed_stage(
    tmp_path: Path, monkeypatch,
) -> None:
    events = []
    monkeypatch.setattr(
        "merit.bootstrap.reproducibility.build_stages",
        lambda _path: (_ for _ in ()).throw(OSError("build failed")),
    )

    with pytest.raises(OSError, match="build failed"):
        build_reproducibility_evidence(
            tmp_path / "evidence",
            progress=lambda label, status, elapsed: events.append((label, status, elapsed)),
        )

    assert [event[:2] for event in events] == [
        ("public_stage_build", "started"),
        ("public_stage_build", "failed"),
    ]


def test_reproducibility_reuses_report_root_but_not_stage_workspace(
    tmp_path: Path, monkeypatch,
) -> None:
    roots: list[Path] = []
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_stages",
                        lambda path: (roots.append(path), _stages(path))[1])
    monkeypatch.setattr("merit.bootstrap.reproducibility.compare_stage_bytes",
                        lambda _stages: _comparison())

    first = build_reproducibility_evidence(tmp_path / "evidence")
    second = build_reproducibility_evidence(tmp_path / "evidence")

    assert first["schema"] == second["schema"] == SCHEMA
    assert roots[0] != roots[1]
    assert all(not root.exists() for root in roots)


def test_reproducibility_evidence_fails_when_next_stage_canonical_source_differs(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr("merit.bootstrap.reproducibility.build_stages",
                        lambda _path: _stages(tmp_path))
    monkeypatch.setattr("merit.bootstrap.reproducibility.compare_stage_bytes",
                        lambda _stages: (_ for _ in ()).throw(
                            SelfHostingError("stage-1/stage-2 c_source bytes differ")))

    with pytest.raises(ReproducibilityError, match="c_source bytes differ"):
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
