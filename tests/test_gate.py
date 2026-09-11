from __future__ import annotations

from typing import Any
from pathlib import Path
import sys

from scripts import gate


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
