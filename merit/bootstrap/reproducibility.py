"""Stage-0/stage-1/stage-2 reproducibility evidence for the replacement compiler."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import time
from typing import Callable, TypeVar

from merit.bootstrap.native_frontend_driver import (
    ReplacementCompilerStage,
    build_native_replacement_driver,
    build_replacement_compiler_stage,
)
from merit.project.replacement_prepare import NativeReplacementDriver


PROBE_SOURCE = b"module main\nfn main()->i32 { return 7; }\n"
PROBE_TIMEOUT_SECONDS = 60
ProgressReporter = Callable[[str, str, float], None]
TimedValue = TypeVar("TimedValue")


class ReproducibilityError(RuntimeError):
    """Raised when compiler stages disagree under the canonical comparison rule."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _driver_output(driver: NativeReplacementDriver) -> bytes:
    completed = subprocess.run(
        [str(driver.resolved())],
        input=PROBE_SOURCE,
        capture_output=True,
        timeout=PROBE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReproducibilityError(
            f"compiler stage probe failed with exit code {completed.returncode}: {detail}"
        )
    return completed.stdout


def _canonical_stage(stage: ReplacementCompilerStage) -> tuple[bytes, bytes]:
    return stage.c_path.read_bytes(), stage.header_path.read_bytes()


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
    """Build and compare the three compiler stages in fresh isolated workspaces."""

    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    stage0, timings["stage_0_build"] = _timed(
        "stage_0_build",
        lambda: build_native_replacement_driver(output_root / "stage-0" / "merit-frontend"),
        progress,
    )
    stage1, timings["stage_1_build"] = _timed(
        "stage_1_build",
        lambda: build_replacement_compiler_stage(
            output_root / "stage-1" / "merit-frontend", stage0,
        ),
        progress,
    )
    stage2, timings["stage_2_build"] = _timed(
        "stage_2_build",
        lambda: build_replacement_compiler_stage(
            output_root / "stage-2" / "merit-frontend", stage1.driver,
        ),
        progress,
    )

    stage1_canonical = _canonical_stage(stage1)
    stage2_canonical = _canonical_stage(stage2)
    if stage1_canonical != stage2_canonical:
        raise ReproducibilityError(
            "stage-1 and stage-2 canonical generated C/header artifacts differ"
        )

    stage_outputs = []
    for label, driver in (
        ("stage_0_probe", stage0),
        ("stage_1_probe", stage1.driver),
        ("stage_2_probe", stage2.driver),
    ):
        stage_output, timings[label] = _timed(
            label, lambda driver=driver: _driver_output(driver), progress,
        )
        stage_outputs.append(stage_output)
    if not stage_outputs[0] == stage_outputs[1] == stage_outputs[2]:
        raise ReproducibilityError("stage-0/stage-1/stage-2 protocol outputs differ")

    return {
        "schema": "merit-alpha2-reproducibility-v1",
        "status": "passed",
        "comparison_rule": {
            "byte_identical": ["generated_c", "public_header", "probe_protocol_output"],
            "execution_only": ["native_library", "native_driver"],
        },
        "stages": {
            "stage_0": {"driver": str(stage0.resolved())},
            "stage_1": {
                "driver": str(stage1.driver.resolved()),
                "generated_c_sha256": _sha256(stage1.c_path),
                "public_header_sha256": _sha256(stage1.header_path),
            },
            "stage_2": {
                "driver": str(stage2.driver.resolved()),
                "generated_c_sha256": _sha256(stage2.c_path),
                "public_header_sha256": _sha256(stage2.header_path),
            },
        },
        "probe_protocol_sha256": hashlib.sha256(stage_outputs[0]).hexdigest(),
        "isolated_source_staging": True,
        "timings_seconds": {name: round(seconds, 3) for name, seconds in timings.items()},
    }
