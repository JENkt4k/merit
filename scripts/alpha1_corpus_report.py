from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / ".merit" / "gates" / "corpus" / "coverage.json"

# ALPHA2_CLOSURE.md identifies tests/test_epoch_*.py as the established
# Alpha.1 Python reference authority. Keep discovery dynamic so a newly added
# epoch corpus file cannot silently fall outside M6.
REFERENCE_CORPUS = tuple(
    str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")
    for path in sorted((REPOSITORY_ROOT / "tests").glob("test_epoch_*.py"))
)

# This is the M6 same-source convergence proof. Each manifest case is applied
# independently to reference and replacement compilation, including native
# execution for accepted cases and deterministic fail-closed behavior for
# rejected cases.
CONVERGENCE_CORPUS = (
    "tests/bootstrap/test_alpha1_corpus_convergence.py",
)


class CorpusFailure(RuntimeError):
    pass


def _run(name: str, paths: tuple[str, ...]) -> dict[str, object]:
    started = time.monotonic()
    command = [sys.executable, "-m", "pytest", "-q", *paths]
    print(f"\n== alpha.1 corpus: {name} ==", flush=True)
    print("+ " + subprocess.list2cmdline(command), flush=True)
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    duration = round(time.monotonic() - started, 3)
    if completed.returncode != 0:
        raise CorpusFailure(
            f"{name} corpus failed with exit code {completed.returncode}"
        )
    return {
        "status": "passed",
        "duration_seconds": duration,
        "paths": list(paths),
    }


def write_report(destination: Path, payload: dict[str, object]) -> Path:
    if not destination.is_absolute():
        destination = REPOSITORY_ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete Alpha.1 reference and replacement corpus convergence gate."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="coverage report destination",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    payload: dict[str, object] = {
        "schema": "merit-alpha1-corpus-convergence-v1",
        "reference_authority": "tests/test_epoch_*.py",
        "reference_file_count": len(REFERENCE_CORPUS),
        "reference_files": list(REFERENCE_CORPUS),
        "convergence_manifest": "tests/project/alpha1_corpus_v1.json",
        "convergence_evidence": list(CONVERGENCE_CORPUS),
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }

    if not REFERENCE_CORPUS:
        payload.update(
            status="failed",
            error="no Alpha.1 epoch corpus files were discovered",
        )
        report = write_report(args.output, payload)
        print(f"ALPHA1_CORPUS_RESULT=FAIL\nreport={report}", file=sys.stderr)
        return 1

    try:
        payload["reference"] = _run("reference authority", REFERENCE_CORPUS)
        payload["convergence"] = _run(
            "same-source reference/replacement convergence", CONVERGENCE_CORPUS
        )
    except CorpusFailure as exc:
        payload.update(
            status="failed",
            duration_seconds=round(time.monotonic() - started, 3),
            error=str(exc),
        )
        report = write_report(args.output, payload)
        print(f"\nALPHA1_CORPUS_RESULT=FAIL\nreport={report}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    payload.update(
        status="passed",
        duration_seconds=round(time.monotonic() - started, 3),
    )
    report = write_report(args.output, payload)
    print("\nALPHA1_CORPUS_RESULT=PASS")
    print(f"reference_files={len(REFERENCE_CORPUS)}")
    print(f"report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
