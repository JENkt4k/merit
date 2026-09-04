from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = REPOSITORY_ROOT / ".merit" / "gates"

ACCEPTANCE_PROJECTS = (
    "text_pipeline",
    "binary_packet",
    "generic_result",
    "trait_bounds",
    "generic_collections",
    "borrowed_views",
    "bootstrap_lexer",
    "cobol_finance_modernization",
)

FAST_TESTS = (
    "tests/test_alpha2.py",
    "tests/test_alpha3.py",
    "tests/test_alpha4.py",
    "tests/test_alpha5.py",
    "tests/test_binding_ids.py",
    "tests/test_bootstrap_ast_parity.py",
    "tests/test_bootstrap_hir_contract.py",
)

SMOKE_TESTS = (
    "tests/test_alpha2.py",
    "tests/test_binding_ids.py",
)

SUBSYSTEM_TESTS = (
    "tests/bootstrap",
    "tests/project",
)

PARALLEL_TEST_WORKERS = 2
PARALLEL_TEST_DISTRIBUTION = "loadfile"


class GateFailure(RuntimeError):
    pass


@contextmanager
def group(name: str) -> Iterator[None]:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::group::{name}", flush=True)
    else:
        print(f"\n== {name} ==", flush=True)
    try:
        yield
    finally:
        if os.environ.get("GITHUB_ACTIONS"):
            print("::endgroup::", flush=True)


def run(command: list[str], *, cwd: Path = REPOSITORY_ROOT) -> None:
    print("+ " + subprocess.list2cmdline(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise GateFailure(
            f"command failed with exit code {completed.returncode}: "
            + subprocess.list2cmdline(command)
        )


def pytest(
    paths: tuple[str, ...] | list[str],
    *,
    durations: int | None = None,
    fail_fast: bool = False,
    workers: int | None = None,
) -> None:
    command = [sys.executable, "-m", "pytest", "-q"]
    if fail_fast:
        command.append("-x")
    if workers is not None:
        command.extend(("-n", str(workers), "--dist", PARALLEL_TEST_DISTRIBUTION))
    command.extend(paths)
    if durations is not None:
        command.append(f"--durations={durations}")
    run(command)


def verify_project(name: str, path: Path, output: Path | None = None, cwd: Path = REPOSITORY_ROOT) -> None:
    command = [sys.executable, "-m", "merit.project.cli", "verify", str(path)]
    if output is not None:
        command.extend(["-o", str(output)])
    with group(f"acceptance: {name}"):
        run(command, cwd=cwd)


def run_acceptance() -> None:
    for name in ACCEPTANCE_PROJECTS:
        verify_project(name, REPOSITORY_ROOT / "examples" / "projects" / name)

    with tempfile.TemporaryDirectory(prefix="merit-gate-") as scratch:
        scratch_root = Path(scratch)
        for name in ("filesystem_capabilities", "ledger_app"):
            work = scratch_root / name
            work.mkdir(parents=True, exist_ok=True)
            verify_project(
                name,
                REPOSITORY_ROOT / "examples" / "projects" / name,
                output=work / name,
                cwd=work,
            )


def run_corpus() -> None:
    with group("alpha.1 accepted/rejected corpus convergence"):
        run([sys.executable, str(REPOSITORY_ROOT / "scripts" / "alpha1_corpus_report.py")])


def run_acceptance_replacement() -> None:
    with group("alpha.2 M7 replacement acceptance migration"):
        run([sys.executable, str(REPOSITORY_ROOT / "scripts" / "acceptance_replacement_report.py")])


def run_gate(name: str, durations: int | None, *, fail_fast: bool) -> dict[str, object]:
    started = time.monotonic()
    if name == "smoke":
        with group("pytest: smoke"):
            pytest(SMOKE_TESTS, durations=durations, fail_fast=fail_fast)
    elif name == "fast":
        with group("pytest: fast"):
            pytest(FAST_TESTS, durations=durations, fail_fast=fail_fast)
    elif name == "subsystem":
        with group("pytest: bootstrap/project subsystem"):
            pytest(SUBSYSTEM_TESTS, durations=durations, fail_fast=fail_fast, workers=PARALLEL_TEST_WORKERS)
    elif name == "corpus":
        run_corpus()
    elif name == "acceptance":
        run_acceptance()
    elif name == "acceptance-replacement":
        run_acceptance_replacement()
    elif name == "full":
        with group("pytest: full"):
            pytest(["tests"], durations=durations, fail_fast=fail_fast, workers=PARALLEL_TEST_WORKERS)
        run_acceptance()
    else:
        raise AssertionError(name)

    duration = time.monotonic() - started
    return {
        "gate": name,
        "status": "passed",
        "duration_seconds": round(duration, 3),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "acceptance_projects": 10 if name in {"acceptance", "acceptance-replacement", "full"} else 0,
        "corpus_convergence": name == "corpus",
        "replacement_acceptance": name == "acceptance-replacement",
    }


def write_result(name: str, result: dict[str, object], output: Path | None) -> Path:
    destination = output or RESULT_ROOT / name / "result.json"
    if not destination.is_absolute():
        destination = REPOSITORY_ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical cross-platform Merit validation gates.")
    parser.add_argument(
        "gate",
        choices=("smoke", "fast", "subsystem", "corpus", "acceptance", "acceptance-replacement", "full"),
        help="validation level to run",
    )
    parser.add_argument("--durations", nargs="?", type=int, const=50, help="show the N slowest pytest tests (default 50 when flag is present)")
    parser.add_argument("--fail-fast", action="store_true", help="stop pytest at the first failure")
    parser.add_argument("--result-json", type=Path, help="result JSON destination; defaults to .merit/gates/<gate>/result.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.chdir(REPOSITORY_ROOT)
    print("Merit validation gate")
    print(f"gate:       {args.gate}")
    print(f"repository: {REPOSITORY_ROOT}")
    print(f"python:     {sys.executable}")

    started = time.monotonic()
    try:
        result = run_gate(args.gate, args.durations, fail_fast=args.fail_fast)
    except (GateFailure, OSError) as exc:
        result = {
            "gate": args.gate,
            "status": "failed",
            "duration_seconds": round(time.monotonic() - started, 3),
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "error": str(exc),
        }
        destination = write_result(args.gate, result, args.result_json)
        print("\nMERIT_GATE_RESULT=FAIL", file=sys.stderr)
        print(f"result={destination}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    destination = write_result(args.gate, result, args.result_json)
    print()
    print("MERIT_GATE_RESULT=PASS")
    print(f"gate={args.gate}")
    print(f"duration_seconds={result['duration_seconds']}")
    if result["acceptance_projects"]:
        print("acceptance_projects=10/10")
    if result.get("corpus_convergence"):
        print("corpus_convergence=PASS")
    if result.get("replacement_acceptance"):
        print("replacement_acceptance=PASS")
    print(f"result={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
