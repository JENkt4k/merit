from __future__ import annotations

from typing import Any
from pathlib import Path
import json
import sys

from scripts import gate


def test_pytest_cache_uses_writable_merit_state(pytestconfig) -> None:
    assert pytestconfig.getini("cache_dir") == ".merit/pytest-cache"


def test_acceptance_verification_selects_reference_oracle_explicitly(monkeypatch) -> None:
    observed: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(
        gate,
        "run",
        lambda command, *, cwd=gate.REPOSITORY_ROOT: observed.append((command, cwd)),
    )

    project = Path("example-project")
    gate.verify_project("example", project)

    assert observed == [
        ([
            sys.executable,
            "-m",
            "merit.project.cli",
            "verify",
            str(project),
            "--compiler",
            "reference",
        ], gate.REPOSITORY_ROOT),
    ]


def test_full_gate_runs_replacement_acceptance_once_as_reported_phase(monkeypatch) -> None:
    events: list[tuple[str, Any]] = []

    def record_pytest(paths, **kwargs) -> None:
        events.append(("pytest", (tuple(paths), kwargs)))

    monkeypatch.setattr(gate, "pytest", record_pytest)
    monkeypatch.setattr(
        gate,
        "run_acceptance_replacement",
        lambda: events.append(("replacement", None)),
    )
    monkeypatch.setattr(
        gate,
        "run_acceptance",
        lambda: events.append(("acceptance", None)),
    )

    result = gate.run_gate("full", 50, fail_fast=True)

    assert events == [
        (
            "pytest",
            (
                ("tests", f"--ignore={gate.M7_ACCEPTANCE_TEST}"),
                {"durations": 50, "fail_fast": True, "workers": 2},
            ),
        ),
        ("replacement", None),
        ("acceptance", None),
    ]
    assert result["replacement_acceptance"] is True


def test_hosted_full_phases_preserve_canonical_full_work(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(gate, "pytest", lambda *args, **kwargs: events.append("pytest"))
    monkeypatch.setattr(gate, "run_acceptance_replacement", lambda: events.append("replacement"))
    monkeypatch.setattr(gate, "run_acceptance", lambda: events.append("acceptance"))

    first = gate.run_gate("full-pytest", 50, fail_fast=False)
    second = gate.run_gate("full-acceptance", 50, fail_fast=False)

    assert events == ["pytest", "replacement", "acceptance"]
    assert first["replacement_acceptance"] is False
    assert second["replacement_acceptance"] is True
    assert second["acceptance_projects"] == 10


def test_isolated_bundle_runs_every_collected_case_in_fresh_batches(monkeypatch) -> None:
    cases = [f"{gate.BOOTSTRAP_BUNDLE_TEST}::case_{index}" for index in range(11)]
    collected = type("Collected", (), {
        "returncode": 0, "stdout": "\n".join(cases) + "\n\n11 tests collected\n", "stderr": "",
    })()
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: collected)
    monkeypatch.setattr(gate, "pytest", lambda paths, **kwargs: commands.append(tuple(paths)))

    assert gate.pytest_isolated_bootstrap_bundle(fail_fast=False) == 11
    assert commands == [(case,) for case in cases]


def test_bootstrap_bundle_shards_cover_every_case_once(monkeypatch) -> None:
    cases = [f"{gate.BOOTSTRAP_BUNDLE_TEST}::case_{index}" for index in range(11)]
    collected = type("Collected", (), {
        "returncode": 0, "stdout": "\n".join(cases) + "\n\n11 tests collected\n", "stderr": "",
    })()
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: collected)
    monkeypatch.setattr(gate, "pytest", lambda paths, **kwargs: commands.append(tuple(paths)))

    counts = [gate.pytest_isolated_bootstrap_bundle(
        fail_fast=False, shard_index=index, shard_count=4,
    ) for index in range(4)]

    assert counts == [3, 3, 3, 2]
    assert sorted(case for batch in commands for case in batch) == sorted(cases)
    assert all(len(batch) == 1 for batch in commands)


def test_isolated_full_gate_excludes_only_the_separately_covered_file(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(gate, "pytest_isolated_bootstrap_bundle", lambda **kwargs: 368)
    monkeypatch.setattr(gate, "pytest", lambda paths, **kwargs: calls.append(tuple(paths)))

    result = gate.run_gate("full-pytest", None, fail_fast=False, isolate_bootstrap_bundle=True)

    assert calls == [(
        "tests", f"--ignore={gate.M7_ACCEPTANCE_TEST}",
        f"--ignore={gate.BOOTSTRAP_BUNDLE_TEST}",
    )]
    assert result["isolated_bootstrap_cases"] == 368


def test_hosted_full_pytest_excludes_bundle_only_when_shards_cover_it(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(gate, "pytest", lambda paths, **kwargs: calls.append(tuple(paths)))

    gate.run_gate("full-pytest", None, fail_fast=False, exclude_bootstrap_bundle=True)

    assert calls == [(
        "tests", f"--ignore={gate.M7_ACCEPTANCE_TEST}",
        f"--ignore={gate.BOOTSTRAP_BUNDLE_TEST}",
    )]


def test_subsystem_gate_leaves_m7_for_dedicated_gate(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    def record_pytest(paths, **kwargs) -> None:
        calls.append((tuple(paths), kwargs))

    monkeypatch.setattr(gate, "pytest", record_pytest)

    gate.run_gate("subsystem", None, fail_fast=False)

    assert calls == [
        (
            (*gate.SUBSYSTEM_TESTS, f"--ignore={gate.M7_ACCEPTANCE_TEST}"),
            {"durations": None, "fail_fast": False, "workers": 2},
        )
    ]


def test_pr_gate_runs_bounded_native_checks_and_corpus_not_full(monkeypatch) -> None:
    events: list[tuple[str, Any]] = []

    def record_pytest(paths, **kwargs) -> None:
        events.append(("pytest", (tuple(paths), kwargs)))

    monkeypatch.setattr(gate, "pytest", record_pytest)
    monkeypatch.setattr(gate, "run_corpus", lambda: events.append(("corpus", None)))
    monkeypatch.setattr(
        gate, "run_acceptance_replacement",
        lambda: events.append(("replacement", None)),
    )
    monkeypatch.setattr(gate, "run_acceptance", lambda: events.append(("acceptance", None)))

    result = gate.run_gate("pr", 10, fail_fast=True)

    assert events == [
        (
            "pytest",
            (
                (*gate.FAST_TESTS, *gate.PR_INTEGRATION_TESTS),
                {"durations": 10, "fail_fast": True, "workers": 2},
            ),
        ),
        ("corpus", None),
    ]
    assert result["corpus_convergence"] is True
    assert result["replacement_acceptance"] is False
    assert result["acceptance_projects"] == 0


def test_reproducibility_gate_preserves_versioned_report(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "reproducibility" / "result.json"
    report.parent.mkdir(parents=True)
    payload = {"schema": "merit-public-stage-reproducibility-v2", "status": "passed",
               "duration_seconds": 4.0, "probe_protocol_sha256": "digest"}
    report.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(gate, "RESULT_ROOT", tmp_path)
    calls = []
    monkeypatch.setattr(gate.subprocess, "run", lambda command, **_kwargs: (
        calls.append(command), type("Completed", (), {"returncode": 0})()
    )[1])

    assert gate.run_gate("reproducibility", None, fail_fast=False) == payload
    assert calls == [[sys.executable, str(gate.REPOSITORY_ROOT / "scripts" / "reproducibility_report.py")]]


def test_reproducibility_gate_preserves_versioned_failure(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "reproducibility" / "result.json"
    report.parent.mkdir(parents=True)
    payload = {"schema": "merit-public-stage-reproducibility-v2", "status": "failed",
               "error": "stage build failed"}
    report.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(gate, "RESULT_ROOT", tmp_path)
    monkeypatch.setattr(gate.subprocess, "run", lambda *_args, **_kwargs: type(
        "Completed", (), {"returncode": 1}
    )())
    assert gate.run_gate("reproducibility", None, fail_fast=False) == payload


def test_self_hosting_gate_preserves_versioned_report(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "self-hosting" / "result.json"
    report.parent.mkdir(parents=True)
    payload = {"schema": "merit-self-hosting-v1", "status": "passed",
               "duration_seconds": 4.0, "acceptance_projects": {"count": 10}}
    report.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(gate, "RESULT_ROOT", tmp_path)
    monkeypatch.setattr(gate.subprocess, "run", lambda *_args, **_kwargs: type(
        "Completed", (), {"returncode": 0}
    )())
    assert gate.run_gate("self-hosting", None, fail_fast=False) == payload
