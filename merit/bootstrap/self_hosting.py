"""Public-interface stage construction and canonical SH5 comparison evidence.

This module transports source bytes, launches compiler processes, and compares
their output. It does not parse or lower Merit source in the production path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable

from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request
from merit.project.replacement import (
    REPLACEMENT_MANIFEST, REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2,
    REPLACEMENT_SCHEMA,
)


ROOT = Path(__file__).resolve().parents[2]
COMPILER_MANIFEST = ROOT / "compiler" / "Merit.toml"
COMPILER_SOURCE = ROOT / "examples" / "projects" / "bootstrap_lexer" / "src"
EXPECTED_COMPILER_MODULES = 46
SCHEMA = "merit-self-hosting-v1"
PROBE_TIMEOUT_SECONDS = 120


class SelfHostingError(RuntimeError):
    """The public stage or canonical comparison contract failed."""


@dataclass(frozen=True)
class Stage:
    name: str
    producer: Path | None
    project: Path
    executable: Path
    command: tuple[str, ...]
    build_seconds: float
    artifacts: dict[str, bytes]
    artifact_hashes: dict[str, str]
    protocol: str | None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_closure(source: Path = COMPILER_SOURCE) -> tuple[tuple[str, str], ...]:
    paths = tuple(sorted(source.rglob("*.mrt")))
    if len(paths) != EXPECTED_COMPILER_MODULES:
        raise SelfHostingError(
            f"compiler source closure has {len(paths)} modules, expected {EXPECTED_COMPILER_MODULES}"
        )
    return tuple((path.relative_to(source).as_posix(), sha256(path.read_bytes())) for path in paths)


def source_closure_digest(rows: tuple[tuple[str, str], ...]) -> str:
    return sha256(json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def isolated_compiler_project(destination: Path) -> Path:
    """Copy only the manifest and exact compiler source closure into a fresh root."""

    if destination.exists():
        raise SelfHostingError(f"isolated compiler root already exists: {destination}")
    project = destination / "compiler"
    source = destination / "examples" / "projects" / "bootstrap_lexer" / "src"
    project.mkdir(parents=True)
    shutil.copy2(COMPILER_MANIFEST, project / "Merit.toml")
    shutil.copytree(COMPILER_SOURCE, source)
    if source_closure(source) != source_closure():
        raise SelfHostingError("isolated compiler source closure differs from repository source")
    if any(path.exists() for path in (project / ".merit", project / "build", source / ".merit")):
        raise SelfHostingError("isolated compiler root contains prior build state")
    return project


def project_command() -> Path:
    executable = Path(sys.executable).with_name(
        "merit-project.exe" if os.name == "nt" else "merit-project"
    )
    if not executable.is_file():
        raise SelfHostingError(f"installed public project command is absent: {executable}")
    return executable


def _executable_path(output: Path) -> Path:
    return output.with_suffix(".exe") if os.name == "nt" else output


def _read_artifacts(project: Path) -> tuple[dict[str, bytes], dict[str, str], str]:
    manifest = project / ".merit" / REPLACEMENT_MANIFEST
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelfHostingError(f"missing or invalid native artifact manifest: {manifest}") from exc
    if payload.get("schema") != REPLACEMENT_SCHEMA:
        raise SelfHostingError("native artifact manifest has an incompatible schema")
    metadata = payload.get("native_artifacts")
    expected = {"canonical_mir", "c_source", "c_header"}
    if not isinstance(metadata, dict) or set(metadata) != expected:
        raise SelfHostingError("native artifact manifest is incomplete")
    artifacts: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    root = manifest.parent.resolve()
    for label in sorted(expected):
        row = metadata[label]
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise SelfHostingError(f"invalid {label} artifact metadata")
        path = (root / row["path"]).resolve()
        try:
            path.relative_to(root)
            content = path.read_bytes()
        except (OSError, ValueError) as exc:
            raise SelfHostingError(f"invalid {label} artifact path") from exc
        digest = sha256(content)
        if not content or digest != row.get("sha256"):
            raise SelfHostingError(f"{label} artifact digest does not match")
        artifacts[label] = content
        digests[label] = digest
    protocol = payload.get("producer_protocol")
    if protocol != REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2:
        raise SelfHostingError("public build did not use the native v4 project protocol")
    return artifacts, digests, protocol


def build_seed(output: Path) -> Stage:
    """Build the trusted stage-0 seed through the independent reference oracle."""

    from merit.project.build import build
    from merit.project.loader import load_project

    started = time.monotonic()
    _, _, executable = build(load_project(COMPILER_MANIFEST), output)
    if not executable.is_file():
        raise SelfHostingError("reference stage-0 compiler was not produced")
    return Stage("stage_0", None, COMPILER_MANIFEST.parent, executable,
                 ("reference-build", str(COMPILER_MANIFEST), str(output)),
                 time.monotonic() - started, {}, {}, None)


def build_public_stage(name: str, project: Path, producer: Path, output: Path) -> Stage:
    """Build one usable compiler solely through the installed public command."""

    command = (str(project_command()), "build", str(project),
               "--compiler-path", str(producer), "-o", str(output))
    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, timeout=3600)
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise SelfHostingError(
            f"{name} public build failed ({completed.returncode}): "
            f"{completed.stderr.decode('utf-8', errors='replace')[-2000:]}"
        )
    executable = _executable_path(output)
    if completed.stdout.strip() != str(executable).encode() or not executable.is_file():
        raise SelfHostingError(f"{name} public build did not return a usable executable")
    artifacts, digests, protocol = _read_artifacts(project)
    return Stage(name, producer, project, executable, command, elapsed,
                 artifacts, digests, protocol)


def probe_request(source: bytes = b"module main\nfn main()->i32 { return 7; }\n") -> bytes:
    return encode_project_request(ProjectRequest(
        "sh5_probe", "src/main.mrt", (ProjectRequestUnit("src/main.mrt", source),),
        header_exports=(),
    ))


def run_probe(executable: Path, request: bytes) -> tuple[int, bytes, bytes]:
    completed = subprocess.run([str(executable)], input=request, capture_output=True,
                               timeout=PROBE_TIMEOUT_SECONDS)
    return completed.returncode, completed.stdout, completed.stderr


def compare_stage_bytes(stages: tuple[Stage, Stage, Stage]) -> dict[str, object]:
    """Compare stage-1/2 artifacts and stage-0/1/2 fixed protocol probes."""

    stage0, stage1, stage2 = stages
    if stage1.protocol != stage2.protocol or not stage1.protocol:
        raise SelfHostingError("stage-1/stage-2 native artifact protocols differ")
    for label in ("canonical_mir", "c_source", "c_header"):
        if stage1.artifacts.get(label) != stage2.artifacts.get(label):
            raise SelfHostingError(f"stage-1/stage-2 {label} bytes differ")
    accepted = probe_request()
    rejected = (accepted[:4] + (99).to_bytes(4, "big") + accepted[8:], probe_request(
        b"module main\nimport missing;\nfn main()->i32 { return 7; }\n"
    ))
    results: dict[str, object] = {}
    for label, request, should_accept in (
        ("accepted", accepted, True),
        ("malformed_request", rejected[0], False),
        ("missing_import", rejected[1], False),
    ):
        observations = tuple(run_probe(stage.executable, request) for stage in stages)
        if len(set(observations)) != 1:
            raise SelfHostingError(f"stage-0/stage-1/stage-2 {label} protocol or diagnostics differ")
        status, stdout, stderr = observations[0]
        if (status == 0) != should_accept:
            raise SelfHostingError(f"{label} has unexpected compiler exit status {status}")
        results[label] = {
            "returncode": status,
            "stdout_sha256": sha256(stdout),
            "stderr_sha256": sha256(stderr),
            "request_sha256": sha256(request),
        }
    return {"canonical_artifact_sha256": stage1.artifact_hashes,
            "fixed_probes": results}


def build_stage_equivalence(
    output_root: Path, *, progress: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Construct fresh public stages and return the bounded core SH5 evidence."""

    if output_root.exists():
        raise SelfHostingError(f"self-hosting evidence root already exists: {output_root}")
    output_root.mkdir(parents=True)
    stage0 = build_seed(output_root / "stage-0" / "merit-frontend")
    stages = [stage0]
    for name in ("stage_1", "stage_2"):
        if progress:
            progress(name, "started")
        project = isolated_compiler_project(output_root / f"{name}-source")
        producer = stages[-1].executable
        stage = build_public_stage(name, project, producer,
                                   output_root / name / "merit-frontend")
        stages.append(stage)
        if progress:
            progress(name, "passed")
    comparison = compare_stage_bytes((stages[0], stages[1], stages[2]))
    rows = source_closure()
    return {
        "schema": SCHEMA,
        "status": "stage-equivalence-passed",
        "source_closure": {"count": len(rows), "digest_sha256": source_closure_digest(rows),
                           "paths": [path for path, _ in rows]},
        "stages": {stage.name: {
            "producer": str(stage.producer) if stage.producer else "reference-oracle",
            "executable": str(stage.executable), "command": list(stage.command),
            "project": str(stage.project), "build_seconds": round(stage.build_seconds, 3),
            "protocol": stage.protocol, "artifact_sha256": stage.artifact_hashes,
        } for stage in stages},
        "isolated_source_build_cache_roots": True,
        "comparison": comparison,
    }
