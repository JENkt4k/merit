from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from merit.bootstrap.reproducibility import ReproducibilityError, build_reproducibility_evidence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / ".merit" / "gates" / "reproducibility" / "result.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and compare Merit replacement compiler stages.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    started = time.monotonic()
    timings: dict[str, float] = {}

    def report_progress(label: str, status: str, elapsed: float) -> None:
        if status == "started":
            print(f"{label}: START", flush=True)
            return
        timings[label] = round(elapsed, 3)
        print(f"{label}: {status.upper()} ({elapsed:.3f}s)", flush=True)

    try:
        payload = build_reproducibility_evidence(
            output.parent / "artifacts",
            progress=report_progress,
        )
    except (OSError, ReproducibilityError, subprocess.SubprocessError) as exc:
        payload = {"schema": "merit-alpha2-reproducibility-v1", "status": "failed", "error": str(exc)}
    payload["timings_seconds"] = timings
    payload["duration_seconds"] = round(time.monotonic() - started, 3)
    payload["python"] = sys.version.split()[0]
    payload["platform"] = sys.platform
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = payload["status"] == "passed"
    print(f"M9_REPRODUCIBILITY_RESULT={'PASS' if passed else 'FAIL'}")
    print(f"result={output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
