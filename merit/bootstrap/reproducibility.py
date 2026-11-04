"""Versioned public-stage reproducibility evidence for the replacement compiler.

The released Alpha.2 M9 v1 report is historical. The current v2 gate compares
the same canonical C/header/probe contract, but builds stages through the public
SH5 interface rather than the retired bundle-only private stage helper.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import time
from typing import Callable, TypeVar

from merit.bootstrap.self_hosting import (
    SelfHostingError,
    build_stages,
    compare_stage_bytes,
)


ProgressReporter = Callable[[str, str, float], None]
TimedValue = TypeVar("TimedValue")
SCHEMA = "merit-public-stage-reproducibility-v2"


class ReproducibilityError(RuntimeError):
    """Raised when compiler stages disagree under the canonical comparison rule."""


def _timed(
    label: str,
    action: Callable[[], TimedValue],
    progress: ProgressReporter | None,
) -> tuple[TimedValue, float]:
    if progress is not None:
        progress(label, "started", 0.0)
    started = time.monotonic()
    try:
        result = action()
    except Exception:
        elapsed = time.monotonic() - started
        if progress is not None:
            progress(label, "failed", elapsed)
        raise
    elapsed = time.monotonic() - started
    if progress is not None:
        progress(label, "passed", elapsed)
    return result, elapsed


def build_reproducibility_evidence(
    output_root: Path,
    *,
    progress: ProgressReporter | None = None,
) -> dict[str, object]:
    """Compare fresh public stages without changing the archived M9 v1 report."""

    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix="public-stage-", dir=output_root) as scratch:
        try:
            stages, timings["public_stage_build"] = _timed(
                "public_stage_build",
                lambda: build_stages(Path(scratch) / "stages"),
                progress,
            )
            comparison, timings["canonical_comparison"] = _timed(
                "canonical_comparison", lambda: compare_stage_bytes(stages), progress,
            )
        except SelfHostingError as exc:
            raise ReproducibilityError(str(exc)) from exc
        stage0, stage1, stage2 = stages
        artifacts = comparison["canonical_artifact_sha256"]
        probe = comparison["fixed_probes"]["accepted"]

    return {
        "schema": SCHEMA,
        "status": "passed",
        "supersedes": "merit-alpha2-reproducibility-v1",
        "comparison_rule": {
            "byte_identical": ["generated_c", "public_header", "probe_protocol_output"],
            "execution_only": ["native_executable"],
        },
        "stages": {
            "stage_0": {"driver": str(stage0.executable)},
            "stage_1": {
                "driver": str(stage1.executable),
                "public_command": list(stage1.command),
                "generated_c_sha256": artifacts["c_source"],
                "public_header_sha256": artifacts["c_header"],
            },
            "stage_2": {
                "driver": str(stage2.executable),
                "public_command": list(stage2.command),
                "generated_c_sha256": artifacts["c_source"],
                "public_header_sha256": artifacts["c_header"],
            },
        },
        "probe_protocol_sha256": probe["stdout_sha256"],
        "probe_request_sha256": probe["request_sha256"],
        "isolated_source_staging": True,
        "timings_seconds": {name: round(seconds, 3) for name, seconds in timings.items()},
    }
