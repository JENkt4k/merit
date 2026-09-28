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
from merit.project.loader import LoadedProject
from merit.project.replacement_loader import ReplacementLoadedProject
from merit.project.replacement import REPLACEMENT_MANIFEST, REPLACEMENT_SCHEMA, ReplacementProjectError
from merit.project.project_request import (
    encode_loaded_project_request,
)

DRIVER_PROTOCOL = "merit-project-request-v1/resolved-source-function-bundle-v3"
# Bounded per-unit ceiling, not evidence of acceptable compiler throughput.
# The bootstrap-lexer M7 case still exceeds this limit; repeated native type
# and callable analysis must be fixed rather than raising the timeout again.
DRIVER_TIMEOUT_SECONDS = 900


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


def _driver_environment(source_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "MERIT_REPLACEMENT_PROTOCOL": DRIVER_PROTOCOL,
            "MERIT_REPLACEMENT_SOURCE_PATH": str(source_path.resolve()),
        }
    )
    environment.pop("MERIT_REPLACEMENT_FUNCTION_INDEX", None)
    return environment


def _run_driver(
    driver: NativeReplacementDriver,
    request: bytes,
    *,
    project_name: str,
    source_path: Path,
):
    executable = driver.resolved()
    try:
        completed = subprocess.run(
            [str(executable)],
            input=request,
            capture_output=True,
            env=_driver_environment(source_path),
            timeout=DRIVER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReplacementProjectError(
            f"replacement driver timed out after {DRIVER_TIMEOUT_SECONDS}s "
            f"for project {project_name!r}"
        ) from exc
    except OSError as exc:
        raise ReplacementProjectError(f"replacement driver could not start: {exc}") from exc
    try:
        stdout = completed.stdout.decode("utf-8")
        stderr = completed.stderr.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReplacementProjectError(
            f"replacement driver emitted non-UTF-8 output for project {project_name!r}"
        ) from exc
    if completed.returncode != 0:
        stderr = stderr.strip()
        stdout = stdout.strip()
        streams = []
        if stderr:
            streams.append(f"stderr={stderr}")
        if stdout:
            streams.append(f"stdout={stdout[-1200:]}")
        if not streams:
            streams.append("no driver output")
        raise ReplacementProjectError(
            f"replacement driver failed for project {project_name!r} with exit code "
            f"{completed.returncode}: {'; '.join(streams)}"
        )
    try:
        values = tuple(int(line.strip()) for line in stdout.splitlines() if line.strip())
    except ValueError as exc:
        raise ReplacementProjectError(
            f"replacement driver emitted non-integer bundle data for project {project_name!r}"
        ) from exc
    if not values:
        raise ReplacementProjectError(
            f"replacement driver emitted no bundle for project {project_name!r}"
        )
    try:
        bundle = decode_resolved_source_function_bundle(values)
    except ResolvedSourceFunctionBundleError as exc:
        raise ReplacementProjectError(
            f"replacement driver emitted invalid bundle for project {project_name!r}: {exc}"
        ) from exc
    if not bundle.module_name:
        raise ReplacementProjectError("replacement driver response has no native module identity")
    return bundle


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
    project: LoadedProject | ReplacementLoadedProject,
    driver: NativeReplacementDriver,
) -> PreparedReplacementArtifacts:
    """Run the native replacement driver and publish all resolved functions atomically."""

    artifact_dir = project.manifest.root / ".merit"
    staged: list[tuple[Path, str]] = []
    manifest_functions: list[dict[str, object]] = []
    snapshot_paths: list[Path] = []

    request = encode_loaded_project_request(project)
    bundle = _run_driver(
        driver,
        request,
        project_name=project.manifest.name,
        source_path=project.manifest.entry_path,
    )
    try:
        project_source = bytes(bundle.functions[0].effective_source_bytes).decode("utf-8")
    except (IndexError, UnicodeDecodeError) as exc:
        raise ReplacementProjectError("replacement driver response has no UTF-8 effective source") from exc
    digest = _source_digest(project_source)
    capability_names = {str(index): name for index, name in enumerate(bundle.capability_names)}
    for function_index, values in enumerate(bundle.encoded_snapshots):
        filename = f"replacement-{bundle.module_name}-{function_index}.snapshot"
        path = artifact_dir / filename
        staged.append((path, "\n".join(str(value) for value in values) + "\n"))
        snapshot_paths.append(path)
        manifest_functions.append(
            {
                "module": bundle.module_name,
                "function_index": function_index,
                "snapshot": filename,
                "source_sha256": digest,
                "capability_names": capability_names,
                "project_source": "replacement-project.source",
                "request_sha256": hashlib.sha256(request).hexdigest(),
            }
        )

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
