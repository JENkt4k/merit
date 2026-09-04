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
DRIVER_TIMEOUT_SECONDS = 120


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
            f"for module {unit.module!r}"
        ) from exc
    except OSError as exc:
        raise ReplacementProjectError(f"replacement driver could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostics"
        raise ReplacementProjectError(
            f"replacement driver failed for module {unit.module!r} with exit code "
            f"{completed.returncode}: {detail}"
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
