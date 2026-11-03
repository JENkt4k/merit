"""Build and record the versioned SH5 public-stage equivalence evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from merit.bootstrap.self_hosting import SCHEMA, SelfHostingError, build_self_hosting_evidence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".merit" / "gates" / "self-hosting" / "result.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the complete Merit self-hosting evidence gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    started = time.monotonic()

    def progress(name: str, status: str) -> None:
        print(f"{name}: {status.upper()}", flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix="merit-sh5-") as scratch:
            payload = build_self_hosting_evidence(
                Path(scratch) / "evidence", progress=progress,
            )
    except (OSError, SelfHostingError, subprocess.SubprocessError, ValueError) as exc:
        payload = {
            "schema": SCHEMA,
            "status": "failed",
            "error": str(exc),
            "duration_seconds": round(time.monotonic() - started, 3),
            "python": sys.version.split()[0],
            "platform": sys.platform,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = payload["status"] == "passed"
    print(f"MERIT_SELF_HOSTING_RESULT={'PASS' if passed else 'FAIL'}")
    print(f"result={output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
