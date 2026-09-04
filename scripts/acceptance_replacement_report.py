from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / ".merit" / "gates" / "acceptance-replacement" / "coverage.json"
EVIDENCE = "tests/project/test_acceptance_replacement_migration.py"
PROJECTS = [
    "text_pipeline",
    "binary_packet",
    "generic_result",
    "trait_bounds",
    "generic_collections",
    "borrowed_views",
    "bootstrap_lexer",
    "cobol_finance_modernization",
    "filesystem_capabilities",
    "ledger_app",
]


def write_report(destination: Path, payload: dict[str, object]) -> Path:
    if not destination.is_absolute():
        destination = REPOSITORY_ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Alpha.2 M7 replacement acceptance migration evidence.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    started = time.monotonic()
    command = [sys.executable, "-m", "pytest", "-q", EVIDENCE]
    print("== Alpha.2 M7 replacement acceptance migration ==", flush=True)
    print("+ " + subprocess.list2cmdline(command), flush=True)
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    payload: dict[str, object] = {
        "schema": "merit-alpha2-m7-acceptance-migration-v1",
        "status": "passed" if completed.returncode == 0 else "failed",
        "duration_seconds": round(time.monotonic() - started, 3),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "project_count": len(PROJECTS),
        "projects": PROJECTS,
        "mandatory_exact_decimal_application": "ledger_app",
        "evidence": EVIDENCE,
        "replacement_fallback_allowed": False,
    }
    if completed.returncode != 0:
        payload["error"] = f"replacement acceptance evidence failed with exit code {completed.returncode}"
    report = write_report(args.output, payload)
    print(f"\nM7_ACCEPTANCE_RESULT={'PASS' if completed.returncode == 0 else 'FAIL'}")
    print(f"acceptance_projects={'10/10' if completed.returncode == 0 else 'incomplete'}")
    print(f"report={report}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
