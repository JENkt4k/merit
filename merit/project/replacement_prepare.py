"""Native replacement frontend -> replacement project artifact publication.

This module is orchestration only. A first-class replacement driver executable
receives one source unit on stdin and emits a versioned multi-function
resolved-source bundle as newline-separated integers on stdout. Python validates
transport/framing, records source identity, and publishes project artifacts
atomically. It never parses or semantically lowers the target source.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from merit.bootstrap.resolved_source_function_bundle import (
    ResolvedSourceFunctionBundleError,
    decode_resolved_source_function_bundle,
)
from merit.project.loader import LoadedProject, SourceUnit
from merit.project.replacement import REPLACEMENT_MANIFEST, REPLACEMENT_SCHEMA, ReplacementProjectError
from merit.project.replacement_source import canonical_replacement_project_source

DRIVER_PROTOCOL = "resolved-source-function-bundle-v1"
# The bootstrap lexer is the largest M7 acceptance unit and currently exceeds
# the old 120-second diagnostic ceiling on hosted runners. Keep a bounded
# per-unit timeout while allowing the acceptance gate to measure it to
# completion; M7 performance work can then use the observed duration rather
# than terminating the native frontend before it reports a result.
DRIVER_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class NativeReplacementDriver:
    """Concrete executable boundary for the native replacement frontend.

    The driver is intentionally a single executable path rather than an
    arbitrary command vector. That keeps the project build contract tied to one
    native frontend artifact and prevents shell/interpreter wrappers from
    becoming part of the production replacement protocol.
    """

    executable: Path

    def resolved(self) -> Path:
        path = self.executable.expanduser().resolve()
        if not path.is_file():
            raise ReplacementProjectError(
                f"replacement driver executable does not exist: {path}"
            )
        return path


@dataclass(frozen=True)
class PreparedReplacementArtifacts:
    manifest_path: Path
    snapshot_paths: tuple[Path, ...]


def _source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _driver_environment(unit: SourceUnit) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "MERIT_REPLACEMENT_PROTOCOL": DRIVER_PROTOCOL,
            "MERIT_REPLACEMENT_MODULE": unit.module,
            "MERIT_REPLACEMENT_SOURCE_PATH": str(unit.path.resolve()),
        }
    )
    environment.pop("MERIT_REPLACEMENT_FUNCTION_INDEX", None)
    return environment


def _failure_source_candidates(source: str, status: int | None) -> str:
    """Return compact source-location hints for native replacement failures.

    This is diagnostics only. It does not participate in replacement semantic
    lowering or alter the source presented to the native frontend.
    """

    patterns: tuple[str, ...]
    stage = "unclassified"
    if status == 4721:
        # native driver +1000 -> from_source +1000 -> from_source_types +1000
        # -> assembly +1000 -> semantics +700 -> ownership-control status 21.
        stage = "resolved ownership lowering: inner status 21"
        patterns = (r"\bdrop\s*\(", r"\bvec_drop\s*<", r"\breturn\b")
    elif status == 4368:
        stage = "native source expression/call lowering"
        patterns = (r"\bfile_read\s*\(", r"\bfile_write\s*\(", r"\bwith\s+capability\b")
    elif status == 2105:
        stage = "generic expansion/catalog lowering"
        patterns = (r"<[^>]+>", r"\bVec\s*<", r"\bOption\s*<", r"\bResult\s*<")
    elif status == 4905:
        stage = "resolved numeric/ownership assembly"
        patterns = (r"\bdecimal_", r"\bDecimal\b", r"\bdec\b", r"\bwith\s+capability\b")
    else:
        patterns = (r"\bdrop\s*\(", r"\breturn\b", r"\bwith\s+capability\b")

    compiled = tuple(re.compile(pattern) for pattern in patterns)
    hits: list[str] = []
    for line_number, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.search(line) for pattern in compiled):
            hits.append(f"L{line_number}: {stripped[:180]}")
            if len(hits) == 12:
                break
    if not hits:
        return f"stage={stage}; source candidates=none"
    return f"stage={stage}; source candidates=" + " | ".join(hits)


def _driver_status(stderr: str) -> int | None:
    match = re.search(r"replacement driver status\s+(-?\d+)", stderr)
    if match is None:
        return None
    return int(match.group(1))


def _run_driver(driver: NativeReplacementDriver, unit: SourceUnit) -> tuple[tuple[int, ...], ...]:
    executable = driver.resolved()
    try:
        completed = subprocess.run(
            [str(executable)],
            input=unit.parser_source,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            env=_driver_environment(unit),
            timeout=DRIVER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReplacementProjectError(
            f"replacement driver timed out after {DRIVER_TIMEOUT_SECONDS}s "
            f"for module {unit.module!r}; "
            f"{_failure_source_candidates(unit.parser_source, None)}"
        ) from exc
    except OSError as exc:
        raise ReplacementProjectError(f"replacement driver could not start: {exc}") from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        status = _driver_status(stderr)
        streams = []
        if stderr:
            streams.append(f"stderr={stderr}")
        if stdout:
            streams.append(f"stdout={stdout[-1200:]}")
        if not streams:
            streams.append("no driver output")
        diagnostic = _failure_source_candidates(unit.parser_source, status)
        raise ReplacementProjectError(
            f"replacement driver failed for module {unit.module!r} with exit code "
            f"{completed.returncode}: {'; '.join(streams)}; {diagnostic}"
        )
    try:
        values = tuple(int(line.strip()) for line in completed.stdout.splitlines() if line.strip())
    except ValueError as exc:
        raise ReplacementProjectError(
            f"replacement driver emitted non-integer bundle data for module {unit.module!r}"
        ) from exc
    if not values:
        raise ReplacementProjectError(
            f"replacement driver emitted no bundle for module {unit.module!r}"
        )
    try:
        bundle = decode_resolved_source_function_bundle(values)
    except ResolvedSourceFunctionBundleError as exc:
        raise ReplacementProjectError(
            f"replacement driver emitted invalid bundle for module {unit.module!r}: {exc}"
        ) from exc
    return bundle.encoded_snapshots


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_replacement_artifacts(
    project: LoadedProject,
    driver: NativeReplacementDriver,
) -> PreparedReplacementArtifacts:
    """Run the native replacement driver and publish all resolved functions atomically."""

    artifact_dir = project.manifest.root / ".merit"
    staged: list[tuple[Path, str]] = []
    manifest_functions: list[dict[str, object]] = []
    snapshot_paths: list[Path] = []

    if len(project.units) == 1:
        driver_units = project.units
        project_source = None
    else:
        project_source = canonical_replacement_project_source(project)
        entry_unit = next(
            unit for unit in project.units
            if unit.path.resolve() == project.manifest.entry_path.resolve()
        )
        driver_units = (
            SourceUnit(
                path=project.manifest.entry_path,
                module=project.manifest.name,
                imports=(),
                parser_source=project_source,
                program=entry_unit.program,
                exports=frozenset().union(*(unit.exports for unit in project.units)),
            ),
        )

    for unit in driver_units:
        snapshots = _run_driver(driver, unit)
        digest = _source_digest(unit.parser_source)
        for function_index, values in enumerate(snapshots):
            filename = f"replacement-{unit.module}-{function_index}.snapshot"
            path = artifact_dir / filename
            staged.append((path, "\n".join(str(value) for value in values) + "\n"))
            snapshot_paths.append(path)
            manifest_functions.append(
                {
                    "module": unit.module,
                    "function_index": function_index,
                    "snapshot": filename,
                    "source_sha256": digest,
                    **({"project_source": "replacement-project.source"} if project_source is not None else {}),
                }
            )

    if project_source is not None:
        staged.append((artifact_dir / "replacement-project.source", project_source))

    payload = {
        "schema": REPLACEMENT_SCHEMA,
        "producer_protocol": DRIVER_PROTOCOL,
        "functions": manifest_functions,
    }
    manifest_path = artifact_dir / REPLACEMENT_MANIFEST

    # Publish snapshots first and the manifest last. Readers either see the old
    # complete generation or the new complete generation; the manifest is the
    # commit point for a prepared replacement build.
    for path, content in staged:
        _atomic_write_text(path, content)
    _atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return PreparedReplacementArtifacts(manifest_path, tuple(snapshot_paths))
