from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from m7_acceptance_inventory import ACCEPTANCE_PROJECTS

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / ".merit" / "gates" / "acceptance-replacement" / "coverage.json"
EVIDENCE = "tests/project/test_acceptance_replacement_migration.py"
TEST_PREFIX = "test_acceptance_project_converges_through_replacement["


def write_report(destination: Path, payload: dict[str, object]) -> Path:
    if not destination.is_absolute():
        destination = REPOSITORY_ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def _project_results(junit_path: Path) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {
        name: {"status": "not-run"} for name in ACCEPTANCE_PROJECTS
    }
    if not junit_path.is_file():
        return results
    root = ET.parse(junit_path).getroot()
    for case in root.iter("testcase"):
        test_name = case.attrib.get("name", "")
        if not test_name.startswith(TEST_PREFIX) or not test_name.endswith("]"):
            continue
        project = test_name[len(TEST_PREFIX):-1]
        if project not in results:
            continue
        row: dict[str, object] = {
            "status": "passed",
            "duration_seconds": round(float(case.attrib.get("time", "0")), 3),
        }
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        problem = failure if failure is not None else error
        if problem is not None:
            row["status"] = "failed" if failure is not None else "error"
            detail = (problem.attrib.get("message") or problem.text or "").strip()
            if detail:
                row["detail"] = detail[-4000:]
        elif skipped is not None:
            row["status"] = "skipped"
            detail = (skipped.attrib.get("message") or skipped.text or "").strip()
            if detail:
                row["detail"] = detail[-4000:]
        results[project] = row
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Alpha.2 M7 replacement acceptance migration evidence.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else REPOSITORY_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    junit_path = output.parent / "pytest-results.xml"
    started = time.monotonic()
    command = [sys.executable, "-m", "pytest", "-q", EVIDENCE, f"--junitxml={junit_path}"]
    print("== Alpha.2 M7 replacement acceptance migration ==", flush=True)
    print("+ " + subprocess.list2cmdline(command), flush=True)
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    project_results = _project_results(junit_path)
    passed_projects = sum(row["status"] == "passed" for row in project_results.values())
    payload: dict[str, object] = {
        "schema": "merit-alpha2-m7-acceptance-migration-v2",
        "status": "passed" if completed.returncode == 0 else "failed",
        "duration_seconds": round(time.monotonic() - started, 3),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "project_count": len(ACCEPTANCE_PROJECTS),
        "passed_project_count": passed_projects,
        "projects": list(ACCEPTANCE_PROJECTS),
        "project_results": project_results,
        "mandatory_exact_decimal_application": "ledger_app",
        "evidence": EVIDENCE,
        "replacement_fallback_allowed": False,
    }
    if completed.returncode != 0:
        payload["error"] = f"replacement acceptance evidence failed with exit code {completed.returncode}"
    report = write_report(output, payload)
    print(f"\nM7_ACCEPTANCE_RESULT={'PASS' if completed.returncode == 0 else 'FAIL'}")
    print(f"acceptance_projects={passed_projects}/{len(ACCEPTANCE_PROJECTS)}")
    print(f"report={report}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
