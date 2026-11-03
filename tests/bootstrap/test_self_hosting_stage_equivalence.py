from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

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


def test_public_build_import_guard_rejects_python_semantic_authority(tmp_path: Path) -> None:
    environment = sh._guarded_environment(tmp_path / "guard")
    completed = subprocess.run(
        [sys.executable, "-c", "import merit.compiler"],
        env=environment, capture_output=True, text=True,
    )
    assert completed.returncode != 0
    assert "Python semantic import in public SH5 build: merit.compiler" in completed.stderr


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


def test_stage_evidence_records_executable_identity_and_protocol(tmp_path: Path, monkeypatch) -> None:
    stages = tuple(_stage(tmp_path, name, {}) for name in
                   ("stage_0", "stage_1", "stage_2"))
    for stage in stages:
        stage.executable.write_bytes(stage.name.encode())
    monkeypatch.setattr(sh, "compare_stage_bytes", lambda _stages: {"fixed_probes": {}})
    evidence = sh.stage_equivalence_evidence(stages)
    for stage in stages:
        row = evidence["stages"][stage.name]
        assert row["executable_sha256"] == sh.sha256(stage.name.encode())
        assert row["protocol"] == sh.REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2


def test_public_stage_equivalence_core(tmp_path: Path, monkeypatch) -> None:
    stages = sh.build_stages(tmp_path / "self-hosting")
    evidence = sh.stage_equivalence_evidence(stages)
    assert evidence["schema"] == sh.SCHEMA
    assert evidence["status"] == "stage-equivalence-passed"
    assert evidence["source_closure"]["count"] == sh.EXPECTED_COMPILER_MODULES
    assert evidence["isolated_source_build_cache_roots"] is True
    assert evidence["comparison"]["canonical_artifact_sha256"]["canonical_mir"]
    assert set(evidence["comparison"]["fixed_probes"]) == {
        "accepted", "malformed_request", "missing_import",
    }
    corpus = json.loads(sh.CORPUS_PATH.read_text(encoding="utf-8"))
    corpus["accepted"] = corpus["accepted"][:1]
    corpus["rejected"] = corpus["rejected"][:1]
    subset = tmp_path / "corpus-smoke.json"
    subset.write_text(json.dumps(corpus), encoding="utf-8")
    monkeypatch.setattr(sh, "CORPUS_PATH", subset)
    convergence = sh.verify_fixed_corpus(stages, tmp_path / "corpus-smoke")
    assert convergence["accepted_count"] == convergence["rejected_count"] == 1
    monkeypatch.setattr(sh, "ACCEPTANCE_NAMES", ("text_pipeline",))
    acceptance = sh.verify_acceptance_projects(stages, tmp_path / "acceptance-smoke")
    assert acceptance["count"] == 1


def test_corpus_evidence_covers_accepted_and_rejected_with_oracle(
    tmp_path: Path, monkeypatch,
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({
        "contract": "alpha1-corpus-convergence-v1",
        "accepted": [{"id": "yes", "files": {"src/main.mrt": "module main\nfn main()->i32 { return 0; }\n"}}],
        "rejected": [{"id": "no", "files": {"src/main.mrt": "module main\nfn main()->i32 { return missing; }\n"}}],
    }), encoding="utf-8")
    monkeypatch.setattr(sh, "CORPUS_PATH", corpus)
    stages = tuple(_stage(tmp_path, name, {}) for name in
                   ("stage_0", "stage_1", "stage_2"))
    oracle_calls = []
    monkeypatch.setattr(sh, "_reference_rejects", lambda root: oracle_calls.append(root))
    monkeypatch.setattr(sh, "_build_case", lambda root, compiler, output: (
        (0, b"0\n", b""), {} if compiler is None else {"c_source": sh.sha256(b"c")},
        (("src/main.mrt", sh.sha256((root / "src/main.mrt").read_bytes())),),
    ))
    monkeypatch.setattr(sh, "run_probe", lambda _executable, _request: (0, b"protocol", b""))
    monkeypatch.setattr(sh, "_stage_rejection", lambda _stage, _root: (1, b"", b"diagnostic"))

    evidence = sh.verify_fixed_corpus(stages, tmp_path / "evidence")
    assert evidence["accepted_count"] == 1
    assert evidence["rejected_count"] == 1
    assert len(oracle_calls) == 1
    assert evidence["rejected"]["no"]["diagnostic_sha256"] == sh.sha256(b"diagnostic")


def test_acceptance_evidence_requires_all_stage_outputs_to_match_oracle(
    tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "examples/projects/one"
    source.mkdir(parents=True)
    (source / "Merit.toml").write_text("[package]\nname='one'\n", encoding="utf-8")
    monkeypatch.setattr(sh, "ROOT", tmp_path)
    monkeypatch.setattr(sh, "ACCEPTANCE_NAMES", ("one",))
    stages = tuple(_stage(tmp_path, name, {}) for name in
                   ("stage_0", "stage_1", "stage_2"))
    monkeypatch.setattr(sh, "_build_case", lambda _root, compiler, _output: (
        (0, b"ok\n", b""), {} if compiler is None else {"c_source": sh.sha256(b"c")},
        (("Merit.toml", sh.sha256(b"manifest")),),
    ))
    evidence = sh.verify_acceptance_projects(stages, tmp_path / "evidence")
    assert evidence["count"] == 1
    assert "one" in evidence["projects"]


def test_full_report_composes_required_evidence_without_private_stage_builder(
    tmp_path: Path, monkeypatch,
) -> None:
    stages = tuple(_stage(tmp_path, name, {}) for name in
                   ("stage_0", "stage_1", "stage_2"))
    calls = []
    monkeypatch.setattr(sh, "build_stages", lambda root, **_kwargs: (
        calls.append(("stages", root)), stages,
    )[1])
    monkeypatch.setattr(sh, "stage_equivalence_evidence", lambda _stages: {
        "schema": sh.SCHEMA, "status": "stage-equivalence-passed",
    })
    monkeypatch.setattr(sh, "verify_fixed_corpus", lambda _stages, root, **_kwargs: (
        calls.append(("corpus", root)), {"accepted_count": 10, "rejected_count": 12},
    )[1])
    monkeypatch.setattr(sh, "verify_acceptance_projects", lambda _stages, root, **_kwargs: (
        calls.append(("acceptance", root)), {"count": 10},
    )[1])
    monkeypatch.setattr(sh, "_python_import_guard", lambda root: (
        calls.append(("guard", root)), {"status": "passed"},
    )[1])
    monkeypatch.setattr(sh, "_git_identity", lambda: {"commit": "abc", "dirty": True})
    monkeypatch.setattr(sh, "_toolchain_identity", lambda: {"path": "cc", "version": "cc 1"})
    evidence = sh.build_self_hosting_evidence(tmp_path / "evidence")
    assert evidence["status"] == "passed"
    assert evidence["schema"] == sh.SCHEMA
    assert evidence["repository"] == {"commit": "abc", "dirty": True}
    assert evidence["fixed_corpus"]["accepted_count"] == 10
    assert evidence["acceptance_projects"]["count"] == 10
    assert [name for name, _root in calls] == ["stages", "corpus", "acceptance", "guard"]


def test_report_failure_writes_versioned_result_and_terminal_marker(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    from scripts import self_hosting_report

    monkeypatch.setattr(self_hosting_report, "build_self_hosting_evidence",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(
                            sh.SelfHostingError("stage disagreement")))
    output = tmp_path / "result.json"
    assert self_hosting_report.main(["--output", str(output)]) == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == sh.SCHEMA
    assert payload["status"] == "failed"
    assert "stage disagreement" in payload["error"]
    assert "MERIT_SELF_HOSTING_RESULT=FAIL" in capsys.readouterr().out
