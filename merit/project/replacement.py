"""Fail-closed production project boundary for replacement compiler artifacts.

Normal project tooling can use this module once a Merit-native frontend has
published resolved-source-function snapshots beside project sources. Python is
only a transport/materialization layer here: it does not parse, check, infer,
or silently fall back to the reference compiler.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

from merit.bootstrap.mir_contract import MirType
from merit.bootstrap.replacement_build import ReplacementBuildError, compile_replacement_artifact
from merit.bootstrap.replacement_project import ReplacementFunctionInput, build_replacement_project_artifact
from merit.project.loader import LoadedProject

REPLACEMENT_MANIFEST = "replacement-build-v1.json"
REPLACEMENT_SCHEMA = "merit-replacement-build-v1"
REPLACEMENT_BUNDLE_PROTOCOL = "resolved-source-function-bundle-v1"


class ReplacementProjectError(ReplacementBuildError):
    """Raised when a project cannot be built through the replacement path."""


@dataclass(frozen=True)
class ReplacementProjectArtifact:
    c_path: Path
    executable: Path


def _type_names(raw: object) -> Mapping[int, MirType] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ReplacementProjectError("replacement type_names must be an object")
    result: dict[int, MirType] = {}
    for key, value in raw.items():
        if not isinstance(value, str) or not value:
            raise ReplacementProjectError("replacement type_names values must be non-empty strings")
        try:
            code = int(key)
        except (TypeError, ValueError) as exc:
            raise ReplacementProjectError("replacement type_names keys must be integer codes") from exc
        result[code] = MirType(value)
    return result


def _capability_names(raw: object) -> Mapping[int, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ReplacementProjectError("replacement capability_names must be an object")
    result: dict[int, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str) or not value:
            raise ReplacementProjectError("replacement capability names must be non-empty strings")
        try:
            code = int(key)
        except (TypeError, ValueError) as exc:
            raise ReplacementProjectError("replacement capability IDs must be integers") from exc
        result[code] = value
    return result


def _source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _validate_bundle_indices(functions: list[object]) -> None:
    next_index: dict[str, int] = {}
    for manifest_index, raw in enumerate(functions):
        if not isinstance(raw, dict):
            raise ReplacementProjectError(f"replacement function {manifest_index} must be an object")
        module_name = raw.get("module")
        function_index = raw.get("function_index")
        if not isinstance(module_name, str) or not module_name:
            raise ReplacementProjectError(
                f"replacement function {manifest_index} has invalid module identity"
            )
        expected = next_index.get(module_name, 0)
        if not isinstance(function_index, int) or isinstance(function_index, bool) or function_index != expected:
            raise ReplacementProjectError(
                f"replacement function indices for module {module_name!r} must be dense and ordered; "
                f"expected {expected}, found {function_index!r}"
            )
        next_index[module_name] = expected + 1


def load_replacement_inputs(project: LoadedProject) -> tuple[ReplacementFunctionInput, ...]:
    """Load native-produced replacement snapshots without semantic fallback."""

    manifest_path = project.manifest.root / ".merit" / REPLACEMENT_MANIFEST
    if not manifest_path.is_file():
        raise ReplacementProjectError(
            "replacement build is unavailable: native frontend artifacts are missing "
            f"({manifest_path}); refusing to fall back to the Python reference compiler"
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplacementProjectError(f"invalid replacement build manifest: {manifest_path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != REPLACEMENT_SCHEMA:
        raise ReplacementProjectError(f"unsupported replacement build manifest schema: {manifest_path}")
    functions = payload.get("functions")
    if not isinstance(functions, list) or not functions:
        raise ReplacementProjectError("replacement build manifest contains no resolved functions")
    if payload.get("producer_protocol") == REPLACEMENT_BUNDLE_PROTOCOL:
        _validate_bundle_indices(functions)

    unit_by_module = {unit.module: unit for unit in project.units}
    resolved: list[ReplacementFunctionInput] = []
    for index, item in enumerate(functions):
        if not isinstance(item, dict):
            raise ReplacementProjectError(f"replacement function {index} must be an object")
        module_name = item.get("module")
        snapshot_name = item.get("snapshot")
        if not isinstance(module_name, str) or module_name not in unit_by_module:
            raise ReplacementProjectError(f"replacement function {index} references unknown module {module_name!r}")
        if not isinstance(snapshot_name, str) or not snapshot_name:
            raise ReplacementProjectError(f"replacement function {index} has no snapshot path")
        snapshot_path = (manifest_path.parent / snapshot_name).resolve()
        try:
            snapshot_path.relative_to(manifest_path.parent.resolve())
        except ValueError as exc:
            raise ReplacementProjectError("replacement snapshot path escapes .merit directory") from exc
        try:
            snapshot_values = tuple(int(line.strip()) for line in snapshot_path.read_text(encoding="utf-8").splitlines() if line.strip())
        except (OSError, ValueError) as exc:
            raise ReplacementProjectError(f"invalid replacement snapshot: {snapshot_path}") from exc
        unit = unit_by_module[module_name]
        expected_digest = item.get("source_sha256")
        if expected_digest is not None:
            if not isinstance(expected_digest, str) or len(expected_digest) != 64:
                raise ReplacementProjectError(
                    f"replacement function {index} has invalid source_sha256"
                )
            actual_digest = _source_digest(unit.parser_source)
            if actual_digest != expected_digest:
                raise ReplacementProjectError(
                    f"replacement artifacts for module {module_name!r} are stale after source changes; "
                    "run prepare-replacement again"
                )
        resolved.append(
            ReplacementFunctionInput.from_values(
                source=unit.parser_source,
                module_name=module_name,
                snapshot_values=snapshot_values,
                capability_names=_capability_names(item.get("capability_names")),
                type_names=_type_names(item.get("type_names")),
            )
        )
    return tuple(resolved)


def build_replacement_project(project: LoadedProject, output: Path) -> ReplacementProjectArtifact:
    """Build only from native-resolved snapshots; never invoke reference semantics."""

    inputs = load_replacement_inputs(project)
    artifact = build_replacement_project_artifact(inputs, module_name=project.manifest.name)
    entry_name = project.program.functions[project.program.entry].name
    main_c = f"int main(void) {{ return (int){entry_name}(); }}"
    c_path, executable = compile_replacement_artifact(
        artifact,
        output,
        main_c=main_c,
        c_flags=project.manifest.c_flags,
    )
    return ReplacementProjectArtifact(c_path=c_path, executable=executable)
