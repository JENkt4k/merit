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

PR_INTEGRATION_TESTS = (
    "tests/test_gate.py",
    "tests/test_release_docs.py",
    "tests/bootstrap/test_replacement_prepare.py::test_v4_preparation_never_imports_python_snapshot_semantics",
    "tests/bootstrap/test_replacement_prepare.py::test_public_v4_build_never_imports_python_semantic_backend",
    "tests/project/test_project_request.py::test_loaded_project_request_canonicalizes_sibling_source_tree",
    "tests/project/test_executable_adapter.py::test_compiler_manifest_uses_complete_source_closure_and_generic_adapter",
    "tests/project/test_native_artifact_entry.py::test_native_compiler_entry_emits_v4_artifacts_without_snapshot_decoder",
    "tests/project/test_sh3_v4_corpus.py::test_sh3_v4_rejects_missing_import_without_python_loader",
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
M7_ACCEPTANCE_TEST = "tests/project/test_acceptance_replacement_migration.py"
BOOTSTRAP_BUNDLE_TEST = "tests/project/test_bootstrap_resolved_source_function_bundle_gate.py"
SH3_DESTRUCTOR_TEST = "tests/project/test_sh3_destructor_artifact.py"
ISOLATED_BATCH_SIZE = 1


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


def pytest_isolated_test_file(
    test_file: str, *, fail_fast: bool, shard_index: int = 0, shard_count: int = 1,
    excluded_files: tuple[str, ...] = (),
) -> int:
    """Run selected cases from one test path in fresh pytest processes."""

    collect = [sys.executable, "-m", "pytest", "--collect-only", "-q", test_file]
    collect.extend(f"--ignore={path}" for path in excluded_files)
    print("+ " + subprocess.list2cmdline(collect), flush=True)
    completed = subprocess.run(collect, cwd=REPOSITORY_ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        raise GateFailure(f"isolated test collection failed: {completed.stdout}\n{completed.stderr}")
    prefix = f"{test_file}::" if test_file.endswith(".py") else f"{test_file}/"
    cases = tuple(
        line for line in completed.stdout.splitlines()
        if line.startswith(prefix) and "::" in line
    )
    if not cases or len(cases) != len(set(cases)):
        raise GateFailure("isolated test collection is empty or contains duplicate cases")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise GateFailure("invalid bootstrap bundle shard")
    cases = cases[shard_index::shard_count]
    if not cases:
        raise GateFailure("isolated test shard contains no cases")
    print(f"isolated_cases={len(cases)} file={test_file} shard={shard_index + 1}/{shard_count}", flush=True)
    for offset in range(0, len(cases), ISOLATED_BATCH_SIZE):
        batch = cases[offset:offset + ISOLATED_BATCH_SIZE]
        print(f"isolated_batch={offset // ISOLATED_BATCH_SIZE + 1}/"
              f"{(len(cases) + ISOLATED_BATCH_SIZE - 1) // ISOLATED_BATCH_SIZE}", flush=True)
        pytest(batch, fail_fast=fail_fast)
    return len(cases)


def pytest_isolated_bootstrap_bundle(
    *, fail_fast: bool, shard_index: int = 0, shard_count: int = 1,
) -> int:
    return pytest_isolated_test_file(
        BOOTSTRAP_BUNDLE_TEST, fail_fast=fail_fast,
        shard_index=shard_index, shard_count=shard_count,
    )


def pytest_isolated_project_shard(
    *, fail_fast: bool, shard_index: int, shard_count: int,
) -> int:
    return pytest_isolated_test_file(
        "tests/project", fail_fast=fail_fast,
        shard_index=shard_index, shard_count=shard_count,
        excluded_files=(M7_ACCEPTANCE_TEST, BOOTSTRAP_BUNDLE_TEST, SH3_DESTRUCTOR_TEST),
    )


def verify_project(name: str, path: Path, output: Path | None = None, cwd: Path = REPOSITORY_ROOT) -> None:
    command = [
        sys.executable,
        "-m",
        "merit.project.cli",
        "verify",
        str(path),
        "--compiler",
        "reference",
    ]
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


def run_reproducibility() -> dict[str, object]:
    with group("public compiler-stage reproducibility v2"):
        command = [sys.executable, str(REPOSITORY_ROOT / "scripts" / "reproducibility_report.py")]
        print("+ " + subprocess.list2cmdline(command), flush=True)
        completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    report = RESULT_ROOT / "reproducibility" / "result.json"
    if not report.is_file():
        raise GateFailure("reproducibility report was not written")
    payload = json.loads(report.read_text(encoding="utf-8"))
    if (completed.returncode == 0) != (payload.get("status") == "passed"):
        raise GateFailure("reproducibility report and process status disagree")
    return payload


def run_self_hosting() -> dict[str, object]:
    with group("SH5 public self-hosting stage equivalence"):
        command = [sys.executable, str(REPOSITORY_ROOT / "scripts" / "self_hosting_report.py")]
        print("+ " + subprocess.list2cmdline(command), flush=True)
        completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    report = RESULT_ROOT / "self-hosting" / "result.json"
    if not report.is_file():
        raise GateFailure("self-hosting report was not written")
    payload = json.loads(report.read_text(encoding="utf-8"))
    if completed.returncode == 0 and payload.get("status") != "passed":
        raise GateFailure("self-hosting report and process status disagree")
    if completed.returncode != 0 and payload.get("status") == "passed":
        raise GateFailure("self-hosting report and process status disagree")
    return payload


def run_gate(
    name: str, durations: int | None, *, fail_fast: bool,
    isolate_bootstrap_bundle: bool = False,
    exclude_bootstrap_bundle: bool = False,
    exclude_destructor: bool = False,
    destructor_only: bool = False,
    bundle_shard: tuple[int, int] | None = None,
    exclude_project: bool = False,
    project_shard: tuple[int, int] | None = None,
) -> dict[str, object]:
    started = time.monotonic()
    isolated_cases = 0
    if exclude_bootstrap_bundle and name != "full-pytest":
        raise GateFailure("bootstrap bundle exclusion requires full-pytest")
    if exclude_bootstrap_bundle and isolate_bootstrap_bundle:
        raise GateFailure("bootstrap bundle cannot be both excluded and isolated")
    if (exclude_destructor or destructor_only) and name != "full-pytest":
        raise GateFailure("destructor isolation requires full-pytest")
    if destructor_only and (exclude_destructor or exclude_bootstrap_bundle or isolate_bootstrap_bundle or bundle_shard is not None):
        raise GateFailure("destructor-only cannot be combined with other isolation options")
    if bundle_shard is not None and name != "full-pytest":
        raise GateFailure("bundle shard requires full-pytest")
    if (exclude_project or project_shard is not None) and name != "full-pytest":
        raise GateFailure("project isolation requires full-pytest")
    if exclude_project and (project_shard is not None or bundle_shard is not None or destructor_only or isolate_bootstrap_bundle):
        raise GateFailure("project exclusion cannot be combined with isolated cases")
    if project_shard is not None and (bundle_shard is not None or destructor_only or isolate_bootstrap_bundle or exclude_bootstrap_bundle or exclude_destructor or exclude_project):
        raise GateFailure("project shard requires full-pytest alone")
    if name == "smoke":
        with group("pytest: smoke"):
            pytest(SMOKE_TESTS, durations=durations, fail_fast=fail_fast)
    elif name == "fast":
        with group("pytest: fast"):
            pytest(FAST_TESTS, durations=durations, fail_fast=fail_fast)
    elif name == "pr":
        with group("pytest: short pull-request gate"):
            pytest(
                [*FAST_TESTS, *PR_INTEGRATION_TESTS],
                durations=durations,
                fail_fast=fail_fast,
                workers=PARALLEL_TEST_WORKERS,
            )
        run_corpus()
    elif name == "subsystem":
        with group("pytest: bootstrap/project subsystem"):
            pytest(
                [*SUBSYSTEM_TESTS, f"--ignore={M7_ACCEPTANCE_TEST}"],
                durations=durations,
                fail_fast=fail_fast,
                workers=PARALLEL_TEST_WORKERS,
            )
    elif name == "corpus":
        run_corpus()
    elif name == "acceptance":
        run_acceptance()
    elif name == "acceptance-replacement":
        run_acceptance_replacement()
    elif name == "reproducibility":
        return run_reproducibility()
    elif name == "self-hosting":
        return run_self_hosting()
    elif name in {"full", "full-pytest"}:
        if project_shard is not None:
            with group("pytest: process-isolated project shard"):
                project_cases = pytest_isolated_project_shard(
                    fail_fast=fail_fast, shard_index=project_shard[0], shard_count=project_shard[1],
                )
            return {
                "gate": name, "status": "passed", "isolated_project_cases": project_cases,
                "project_shard_index": project_shard[0], "project_shard_count": project_shard[1],
                "duration_seconds": round(time.monotonic() - started, 3),
                "python": sys.version.split()[0], "platform": sys.platform,
            }
        if destructor_only:
            with group("pytest: process-isolated destructor artifact probes"):
                destructor_cases = pytest_isolated_test_file(SH3_DESTRUCTOR_TEST, fail_fast=fail_fast)
            return {
                "gate": name, "status": "passed", "isolated_destructor_cases": destructor_cases,
                "duration_seconds": round(time.monotonic() - started, 3),
                "python": sys.version.split()[0], "platform": sys.platform,
            }
        if bundle_shard is not None:
            if name != "full-pytest" or isolate_bootstrap_bundle or exclude_bootstrap_bundle or exclude_destructor:
                raise GateFailure("bundle shard requires full-pytest alone")
            with group("pytest: process-isolated bootstrap bundle shard"):
                isolated_cases = pytest_isolated_bootstrap_bundle(
                    fail_fast=fail_fast, shard_index=bundle_shard[0], shard_count=bundle_shard[1],
                )
            return {
                "gate": name, "status": "passed", "isolated_bootstrap_cases": isolated_cases,
                "bundle_shard_index": bundle_shard[0], "bundle_shard_count": bundle_shard[1],
                "duration_seconds": round(time.monotonic() - started, 3),
                "python": sys.version.split()[0], "platform": sys.platform,
            }
        if isolate_bootstrap_bundle:
            with group("pytest: process-isolated bootstrap bundle probes"):
                isolated_cases = pytest_isolated_bootstrap_bundle(fail_fast=fail_fast)
        with group("pytest: full"):
            pytest(
                ["tests", f"--ignore={M7_ACCEPTANCE_TEST}",
                 *(["--ignore=tests/project"] if exclude_project else []),
                 *([f"--ignore={BOOTSTRAP_BUNDLE_TEST}"] if isolate_bootstrap_bundle or exclude_bootstrap_bundle else []),
                 *([f"--ignore={SH3_DESTRUCTOR_TEST}"] if exclude_destructor else [])],
                durations=durations,
                fail_fast=fail_fast,
                workers=PARALLEL_TEST_WORKERS,
            )
        if name == "full":
            run_acceptance_replacement()
            run_acceptance()
    elif name == "full-acceptance":
        run_acceptance_replacement()
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
        "acceptance_projects": 10 if name in {"acceptance", "acceptance-replacement", "full", "full-acceptance"} else 0,
        "corpus_convergence": name in {"corpus", "pr"},
        "replacement_acceptance": name in {"acceptance-replacement", "full", "full-acceptance"},
        "stage_reproducibility": name == "reproducibility",
        "isolated_bootstrap_cases": isolated_cases,
        "excluded_bootstrap_bundle": exclude_bootstrap_bundle,
        "excluded_destructor": exclude_destructor,
        "excluded_project": exclude_project,
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
        choices=("smoke", "fast", "pr", "subsystem", "corpus", "acceptance", "acceptance-replacement", "reproducibility", "self-hosting", "full", "full-pytest", "full-acceptance"),
        help="validation level to run",
    )
    parser.add_argument("--durations", nargs="?", type=int, const=50, help="show the N slowest pytest tests (default 50 when flag is present)")
    parser.add_argument("--fail-fast", action="store_true", help="stop pytest at the first failure")
    parser.add_argument(
        "--isolate-bootstrap-bundle", action="store_true",
        help="run all bootstrap bundle tests in small fresh pytest processes (hosted Linux memory)",
    )
    parser.add_argument(
        "--exclude-bootstrap-bundle", action="store_true",
        help="exclude bootstrap bundle probes when separate hosted shard jobs cover them",
    )
    parser.add_argument(
        "--bundle-shard", type=str, metavar="INDEX/COUNT",
        help="run only one zero-based shard of process-isolated bootstrap bundle probes",
    )
    parser.add_argument(
        "--exclude-destructor", action="store_true",
        help="exclude destructor artifact probes when a separate hosted job covers them",
    )
    parser.add_argument(
        "--destructor-only", action="store_true",
        help="run destructor artifact probes in fresh one-test pytest processes",
    )
    parser.add_argument(
        "--exclude-project", action="store_true",
        help="exclude project tests when separate hosted shard jobs cover them",
    )
    parser.add_argument(
        "--project-shard", type=str, metavar="INDEX/COUNT",
        help="run one zero-based shard of remaining project tests in fresh pytest processes",
    )
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
        bundle_shard = None
        if args.bundle_shard is not None:
            parts = args.bundle_shard.split("/")
            if len(parts) != 2 or any(not part.isdecimal() for part in parts):
                raise GateFailure("bundle shard must be INDEX/COUNT with decimal integers")
            bundle_shard = (int(parts[0]), int(parts[1]))
        project_shard = None
        if args.project_shard is not None:
            parts = args.project_shard.split("/")
            if len(parts) != 2 or any(not part.isdecimal() for part in parts):
                raise GateFailure("project shard must be INDEX/COUNT with decimal integers")
            project_shard = (int(parts[0]), int(parts[1]))
        result = run_gate(
            args.gate, args.durations, fail_fast=args.fail_fast,
            isolate_bootstrap_bundle=args.isolate_bootstrap_bundle,
            exclude_bootstrap_bundle=args.exclude_bootstrap_bundle,
            exclude_destructor=args.exclude_destructor,
            destructor_only=args.destructor_only,
            bundle_shard=bundle_shard,
            exclude_project=args.exclude_project,
            project_shard=project_shard,
        )
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

    if result.get("status") != "passed":
        destination = write_result(args.gate, result, args.result_json)
        print("\nMERIT_GATE_RESULT=FAIL", file=sys.stderr)
        print(f"result={destination}", file=sys.stderr)
        print(str(result.get("error", "self-hosting gate failed")), file=sys.stderr)
        return 1

    destination = write_result(args.gate, result, args.result_json)
    print()
    print("MERIT_GATE_RESULT=PASS")
    print(f"gate={args.gate}")
    print(f"duration_seconds={result['duration_seconds']}")
    if result.get("acceptance_projects"):
        print("acceptance_projects=10/10")
    if result.get("corpus_convergence"):
        print("corpus_convergence=PASS")
    if result.get("replacement_acceptance"):
        print("replacement_acceptance=PASS")
    if result.get("stage_reproducibility"):
        print("stage_reproducibility=PASS")
    print(f"result={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
