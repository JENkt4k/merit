from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from merit.bootstrap.replacement_mir_adapter import ReplacementFunctionInput
from merit.bootstrap.replacement_project_artifact import (
    ReplacementProjectArtifact as CanonicalReplacementProjectArtifact,
    build_replacement_project_artifact,
    compile_replacement_artifact,
)
from merit.project.loader import LoadedProject


REPLACEMENT_MANIFEST = ".merit/replacement-build-v1.json"


class ReplacementProjectError(Exception):
    pass


@dataclass(frozen=True)
class ReplacementProjectArtifact:
    c_path: Path
    executable: Path


def _source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _capability_names(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(value, str) and value for value in raw):
        raise ReplacementProjectError("replacement capability_names must be a string array")
    return tuple(raw)


def _type_names(raw: object) -> dict[int, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ReplacementProjectError("replacement type_names must be an object")
    result: dict[int, str] = {}
    for key, value in raw.items():
        try:
            code = int(key)
        except (TypeError, ValueError) as exc:
            raise ReplacementProjectError("replacement type_names keys must be integer codes") from exc
        if not isinstance(value, str) or not value:
            raise ReplacementProjectError("replacement type_names values must be non-empty strings")
        result[code] = value
    return result


def _load_manifest(project: LoadedProject) -> dict:
    path = project.manifest.root / REPLACEMENT_MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReplacementProjectError(
            f"replacement build manifest is missing: {path}; run prepare-replacement first"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplacementProjectError(f"invalid replacement build manifest: {path}") from exc
    if not isinstance(data, dict) or data.get("format") != "replacement-build-v1":
        raise ReplacementProjectError("unsupported replacement build manifest format")
    functions = data.get("functions")
    if not isinstance(functions, list) or not functions:
        raise ReplacementProjectError("replacement build manifest must contain functions")
    return data


def load_replacement_inputs(project: LoadedProject) -> tuple[ReplacementFunctionInput, ...]:
    data = _load_manifest(project)
    unit_by_module = {unit.module: unit for unit in project.units}
    resolved: list[ReplacementFunctionInput] = []
    for index, item in enumerate(data["functions"]):
        if not isinstance(item, dict):
            raise ReplacementProjectError(f"replacement function {index} must be an object")
        module_name = item.get("module")
        snapshot = item.get("snapshot")
        if not isinstance(module_name, str) or module_name not in unit_by_module:
            raise ReplacementProjectError(f"replacement function {index} references unknown module")
        if not isinstance(snapshot, str) or not snapshot:
            raise ReplacementProjectError(f"replacement function {index} has invalid snapshot path")
        snapshot_path = (project.manifest.root / ".merit" / snapshot).resolve()
        replacement_root = (project.manifest.root / ".merit").resolve()
        try:
            snapshot_path.relative_to(replacement_root)
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


def _project_entry_name(project: LoadedProject) -> str:
    """Return the conventional executable entry function from the loaded program."""

    entry = next((function for function in project.program.functions if function.name == "main"), None)
    if entry is None:
        raise ReplacementProjectError("replacement executable requires a main function")
    return entry.name


def build_replacement_project(project: LoadedProject, output: Path) -> ReplacementProjectArtifact:
    """Build only from native-resolved snapshots; never invoke reference semantics."""

    inputs = load_replacement_inputs(project)
    artifact = build_replacement_project_artifact(inputs, module_name=project.manifest.name)
    entry_name = _project_entry_name(project)
    main_c = f"int main(void) {{ return (int){entry_name}(); }}"
    c_path, executable = compile_replacement_artifact(
        artifact,
        output,
        main_c=main_c,
        c_flags=project.manifest.c_flags,
    )
    return ReplacementProjectArtifact(c_path=c_path, executable=executable)
