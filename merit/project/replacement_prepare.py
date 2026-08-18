"""Native frontend -> replacement project artifact publication.

This is orchestration only. A producer executable receives one source unit on
stdin and emits a versioned multi-function resolved-source bundle as newline
separated integers on stdout. Python validates transport/framing, records source
identity, and publishes project artifacts atomically. It never parses or
semantically lowers the target source.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Sequence

from merit.bootstrap.resolved_source_function_bundle import (
    ResolvedSourceFunctionBundleError,
    decode_resolved_source_function_bundle,
)
from merit.project.loader import LoadedProject, SourceUnit
from merit.project.replacement import REPLACEMENT_MANIFEST, REPLACEMENT_SCHEMA, ReplacementProjectError

PRODUCER_PROTOCOL = "resolved-source-function-bundle-v1"


@dataclass(frozen=True)
class PreparedReplacementArtifacts:
    manifest_path: Path
    snapshot_paths: tuple[Path, ...]


def _source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _producer_environment(unit: SourceUnit) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "MERIT_REPLACEMENT_PROTOCOL": PRODUCER_PROTOCOL,
            "MERIT_REPLACEMENT_MODULE": unit.module,
            "MERIT_REPLACEMENT_SOURCE_PATH": str(unit.path.resolve()),
        }
    )
    # Remove the v1 per-function selector so producers cannot accidentally keep
    # behaving as one-function-per-source workers under the bundle protocol.
    environment.pop("MERIT_REPLACEMENT_FUNCTION_INDEX", None)
    return environment


def _run_producer(command: Sequence[str], unit: SourceUnit) -> tuple[tuple[int, ...], ...]:
    if not command:
        raise ReplacementProjectError("replacement producer command is empty")
    try:
        completed = subprocess.run(
            list(command),
            input=unit.parser_source,
            text=True,
            capture_output=True,
            env=_producer_environment(unit),
        )
    except OSError as exc:
        raise ReplacementProjectError(f"replacement producer could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostics"
        raise ReplacementProjectError(
            f"replacement producer failed for module {unit.module!r} with exit code "
            f"{completed.returncode}: {detail}"
        )
    try:
        values = tuple(int(line.strip()) for line in completed.stdout.splitlines() if line.strip())
    except ValueError as exc:
        raise ReplacementProjectError(
            f"replacement producer emitted non-integer bundle data for module {unit.module!r}"
        ) from exc
    if not values:
        raise ReplacementProjectError(
            f"replacement producer emitted no bundle for module {unit.module!r}"
        )
    try:
        bundle = decode_resolved_source_function_bundle(values)
    except ResolvedSourceFunctionBundleError as exc:
        raise ReplacementProjectError(
            f"replacement producer emitted invalid bundle for module {unit.module!r}: {exc}"
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
    producer_command: Sequence[str],
) -> PreparedReplacementArtifacts:
    """Run the native producer and publish all resolved functions atomically."""

    artifact_dir = project.manifest.root / ".merit"
    staged: list[tuple[Path, str]] = []
    manifest_functions: list[dict[str, object]] = []
    snapshot_paths: list[Path] = []

    for unit in project.units:
        snapshots = _run_producer(producer_command, unit)
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
                }
            )

    payload = {
        "schema": REPLACEMENT_SCHEMA,
        "producer_protocol": PRODUCER_PROTOCOL,
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
