from __future__ import annotations

from pathlib import Path

import pytest

from merit.bootstrap import self_hosting as sh


def _stage(root: Path, name: str, artifacts: dict[str, bytes]) -> sh.Stage:
    return sh.Stage(name, None, root, root / name, (name,), 0.1, artifacts,
                    {key: sh.sha256(value) for key, value in artifacts.items()},
                    "merit-project-request-v2/resolved-source-function-bundle-v4")


def test_source_closure_is_exact_and_stable(tmp_path: Path) -> None:
    rows = sh.source_closure()
    assert len(rows) == sh.EXPECTED_COMPILER_MODULES
    assert rows == tuple(sorted(rows))
    assert sh.source_closure_digest(rows) == sh.source_closure_digest(rows)
    with pytest.raises(sh.SelfHostingError, match="expected 46"):
        sh.source_closure(tmp_path)


def test_isolated_compiler_project_excludes_build_state(tmp_path: Path) -> None:
    destination = tmp_path / "fresh"
    project = sh.isolated_compiler_project(destination)
    assert (project / "Merit.toml").read_bytes() == sh.COMPILER_MANIFEST.read_bytes()
    assert sh.source_closure(destination / "examples/projects/bootstrap_lexer/src") == sh.source_closure()
    assert not (project / ".merit").exists()
    with pytest.raises(sh.SelfHostingError, match="already exists"):
        sh.isolated_compiler_project(destination)


def test_public_stage_uses_only_installed_command_and_reads_native_artifacts(
    tmp_path: Path, monkeypatch,
) -> None:
    project = tmp_path / "compiler"
    native = project / ".merit"
    native.mkdir(parents=True)
    artifacts = {"canonical_mir": b"mir", "c_source": b"c", "c_header": b"h"}
    metadata = {}
    for label, content in artifacts.items():
        path = f"{label}.txt"
        (native / path).write_bytes(content)
        metadata[label] = {"path": path, "sha256": sh.sha256(content)}
    import json
    (native / "replacement-build-v1.json").write_text(json.dumps({
        "schema": sh.REPLACEMENT_SCHEMA,
        "producer_protocol": "merit-project-request-v2/resolved-source-function-bundle-v4",
        "native_artifacts": metadata,
    }), encoding="utf-8")
    tool = tmp_path / "merit-project"
    tool.write_bytes(b"tool")
    producer = tmp_path / "stage-0"
    producer.write_bytes(b"compiler")
    output = tmp_path / "stage-1"
    monkeypatch.setattr(sh, "project_command", lambda: tool)
    monkeypatch.setattr(sh, "_executable_path", lambda path: path)

    def fake_run(command, **_kwargs):
        output.write_bytes(b"next compiler")
        return type("Completed", (), {"returncode": 0,
                                      "stdout": str(output).encode() + b"\n", "stderr": b""})()

    monkeypatch.setattr(sh.subprocess, "run", fake_run)
    stage = sh.build_public_stage("stage_1", project, producer, output)
    assert stage.command == (str(tool), "build", str(project),
                             "--compiler-path", str(producer), "-o", str(output))
    assert stage.artifacts == artifacts
    assert stage.executable == output

    metadata["canonical_mir"]["sha256"] = "0" * 64
    (native / "replacement-build-v1.json").write_text(json.dumps({
        "schema": sh.REPLACEMENT_SCHEMA,
        "producer_protocol": sh.REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2,
        "native_artifacts": metadata,
    }), encoding="utf-8")
    with pytest.raises(sh.SelfHostingError, match="digest does not match"):
        sh.build_public_stage("stage_1", project, producer, output)


def test_public_stage_fails_closed_when_command_fails(tmp_path: Path, monkeypatch) -> None:
    tool = tmp_path / "merit-project"
    tool.write_bytes(b"tool")
    monkeypatch.setattr(sh, "project_command", lambda: tool)
    monkeypatch.setattr(sh.subprocess, "run", lambda *_args, **_kwargs: type(
        "Completed", (), {"returncode": 1, "stdout": b"", "stderr": b"no compiler"}
    )())
    with pytest.raises(sh.SelfHostingError, match="public build failed"):
        sh.build_public_stage("stage_1", tmp_path / "project", tmp_path / "seed",
                              tmp_path / "next")


def test_stage_comparison_requires_byte_identity_and_fail_closed_diagnostics(
    tmp_path: Path, monkeypatch,
) -> None:
    artifacts = {"canonical_mir": b"mir", "c_source": b"c", "c_header": b"h"}
    stages = tuple(_stage(tmp_path, name, artifacts) for name in
                   ("stage_0", "stage_1", "stage_2"))
    monkeypatch.setattr(sh, "run_probe", lambda _exe, request: (
        (0, b"protocol", b"") if request[:8] == b"MPRQ\x00\x00\x00\x02" and b"missing" not in request
        else (1, b"", b"diagnostic")
    ))
    comparison = sh.compare_stage_bytes(stages)
    assert comparison["canonical_artifact_sha256"]["canonical_mir"] == sh.sha256(b"mir")
    assert comparison["fixed_probes"]["missing_import"]["returncode"] == 1

    changed = _stage(tmp_path, "stage_2", {**artifacts, "canonical_mir": b"changed"})
    with pytest.raises(sh.SelfHostingError, match="canonical_mir bytes differ"):
        sh.compare_stage_bytes((stages[0], stages[1], changed))

    monkeypatch.setattr(sh, "run_probe", lambda exe, _request: (
        (1, b"", b"different") if exe == stages[2].executable else (1, b"", b"diagnostic")
    ))
    with pytest.raises(sh.SelfHostingError, match="protocol or diagnostics differ"):
        sh.compare_stage_bytes(stages)


def test_public_stage_equivalence_core(tmp_path: Path) -> None:
    evidence = sh.build_stage_equivalence(tmp_path / "self-hosting")
    assert evidence["schema"] == sh.SCHEMA
    assert evidence["status"] == "stage-equivalence-passed"
    assert evidence["source_closure"]["count"] == sh.EXPECTED_COMPILER_MODULES
    assert evidence["isolated_source_build_cache_roots"] is True
    assert evidence["comparison"]["canonical_artifact_sha256"]["canonical_mir"]
    assert set(evidence["comparison"]["fixed_probes"]) == {
        "accepted", "malformed_request", "missing_import",
    }
