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
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import TYPE_CHECKING

from merit.project.replacement_loader import ReplacementLoadedProject
from merit.project.replacement import (
    REPLACEMENT_MANIFEST,
    REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL,
    REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2,
    REPLACEMENT_SCHEMA,
    ReplacementProjectError,
)
from merit.project.project_request import (
    encode_loaded_project_request,
)

if TYPE_CHECKING:
    from merit.project.loader import LoadedProject

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
    project_artifact_paths: tuple[Path, ...] = ()


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
    from merit.bootstrap.resolved_source_function_bundle import (
        PROJECT_ARTIFACT_BUNDLE_VERSION,
        ResolvedSourceFunctionBundleError,
        decode_native_project_artifact_transport,
        decode_resolved_source_function_bundle,
    )

    with tempfile.TemporaryFile(mode="w+b") as stdout_file:
        try:
            completed = subprocess.run(
                [str(executable)],
                input=request,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
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
            stderr = completed.stderr.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReplacementProjectError(
                f"replacement driver emitted non-UTF-8 output for project {project_name!r}"
            ) from exc
        if completed.returncode != 0:
            stdout_file.seek(0, os.SEEK_END)
            stdout_file.seek(max(0, stdout_file.tell() - 4800))
            try:
                stdout_tail = stdout_file.read().decode("utf-8").strip()[-1200:]
            except UnicodeDecodeError as exc:
                raise ReplacementProjectError(
                    f"replacement driver emitted non-UTF-8 output for project {project_name!r}"
                ) from exc
            streams = []
            if stderr.strip():
                streams.append(f"stderr={stderr.strip()}")
            if stdout_tail:
                streams.append(f"stdout={stdout_tail}")
            if not streams:
                streams.append("no driver output")
            raise ReplacementProjectError(
                f"replacement driver failed for project {project_name!r} with exit code "
                f"{completed.returncode}: {'; '.join(streams)}"
            )
        stdout_file.seek(0)
        if os.environ.get("MERIT_TRANSPORT_DIAGNOSTIC") == "1":
            stdout_file.seek(0, os.SEEK_END)
            print(f"MERIT_TRANSPORT_STDOUT_BYTES={stdout_file.tell()}", flush=True)
            stdout_file.seek(0)
        try:
            values = (int(line.strip()) for line in stdout_file if line.strip())
            first = next(values, None)
            second = next(values, None)
            third = next(values, None)
            if os.environ.get("MERIT_TRANSPORT_DIAGNOSTIC") == "1":
                print(f"MERIT_TRANSPORT_HEADER={first},{second},{third}", flush=True)
            if first is None:
                raise ReplacementProjectError(
                    f"replacement driver emitted no bundle for project {project_name!r}"
                )
            framed_values = itertools.chain(
                (first,),
                () if second is None else (second,),
                () if third is None else (third,),
                values,
            )
            bundle = (
                decode_native_project_artifact_transport(framed_values)
                if second == PROJECT_ARTIFACT_BUNDLE_VERSION
                else decode_resolved_source_function_bundle(framed_values)
            )
        except ValueError as exc:
            if not isinstance(exc, ResolvedSourceFunctionBundleError):
                raise ReplacementProjectError(
                    f"replacement driver emitted non-integer bundle data for project {project_name!r}"
                ) from exc
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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_replacement_artifacts(
    project: LoadedProject | ReplacementLoadedProject,
    driver: NativeReplacementDriver,
    *,
    header_exports: frozenset[str] | None = None,
) -> PreparedReplacementArtifacts:
    """Run the native replacement driver and publish its versioned artifacts."""

    from merit.bootstrap.resolved_source_function_bundle import NativeProjectArtifactTransport

    artifact_dir = project.manifest.root / ".merit"
    staged: list[tuple[Path, str]] = []
    manifest_functions: list[dict[str, object]] = []
    snapshot_paths: list[Path] = []
    project_artifact_paths: list[Path] = []

    if header_exports is None and project.manifest.executable_adapter is not None:
        header_exports = frozenset({project.manifest.executable_entry or ""})
    request = encode_loaded_project_request(project, header_exports=header_exports)
    bundle = _run_driver(
        driver,
        request,
        project_name=project.manifest.name,
        source_path=project.manifest.entry_path,
    )
    if not isinstance(bundle, NativeProjectArtifactTransport):
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

    producer_protocol = DRIVER_PROTOCOL
    native_artifacts: dict[str, dict[str, str]] | None = None
    if isinstance(bundle, NativeProjectArtifactTransport):
        if not (bundle.canonical_mir_bytes and bundle.c_source_bytes and bundle.c_header_bytes):
            raise ReplacementProjectError(
                "replacement driver response has an incomplete native project artifact set"
            )
        try:
            bundle.canonical_mir_bytes.decode("utf-8")
            bundle.c_source_bytes.decode("utf-8")
            bundle.c_header_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReplacementProjectError(
                "replacement driver response has non-UTF-8 native project artifacts"
            ) from exc
        artifact_payloads = {
            "canonical_mir": ("mir.json", bundle.canonical_mir_bytes),
            "c_source": ("c", bundle.c_source_bytes),
            "c_header": ("h", bundle.c_header_bytes),
        }
        native_artifacts = {}
        for label, (extension, content) in artifact_payloads.items():
            digest = hashlib.sha256(content).hexdigest()
            filename = f"replacement-project-{digest}.{extension}"
            path = artifact_dir / filename
            _atomic_write_bytes(path, content)
            project_artifact_paths.append(path)
            native_artifacts[label] = {
                "path": filename,
                "sha256": digest,
            }
        producer_protocol = (
            REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2
            if header_exports is not None else REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL
        )

    payload = {
        "schema": REPLACEMENT_SCHEMA,
        "producer_protocol": producer_protocol,
        "request_sha256": hashlib.sha256(request).hexdigest(),
        "functions": manifest_functions,
    }
    if native_artifacts is not None:
        payload["native_artifacts"] = native_artifacts
    manifest_path = artifact_dir / REPLACEMENT_MANIFEST

    # V4 artifacts have content-addressed paths, so old manifests remain valid
    # while the next generation is written. The manifest is published last.
    # The legacy snapshot path retains its historical fixed-name publication.
    for path, content in staged:
        _atomic_write_text(path, content)
    _atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return PreparedReplacementArtifacts(
        manifest_path, tuple(snapshot_paths), tuple(project_artifact_paths)
    )
