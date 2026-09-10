"""Project-shaped entry boundary for replacement-compiler artifacts.

This module deliberately does not invoke the Python reference checker/compiler.
It packages source units with the already-resolved snapshots emitted by the
Merit-native frontend and feeds them into the canonical replacement MIR build
boundary.  It is the seam that normal project loading can target while native
multi-function/module snapshot production is completed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping

from merit.bootstrap.mir_contract import MirDestructor, MirModule, MirType
from merit.bootstrap.mir_to_c import emit_c_module
from merit.bootstrap.replacement_build import (
    ReplacementBuildArtifact,
    ReplacementBuildError,
    compile_replacement_artifact,
)
from merit.bootstrap.resolved_source_function_snapshot import (
    decode_resolved_source_function_snapshot,
    materialize_resolved_source_function_snapshot,
)


_OWNED_PAYLOAD_ENUM_DESCRIPTOR_KIND = 2
_UNIT_TYPE_CODE = 14
_UNIT_ENUM_STORAGE = re.compile(r"\bvoid (variant_\d+);")


@dataclass(frozen=True)
class ReplacementFunctionInput:
    """One source function plus semantic records produced by native lowering."""

    source: str
    module_name: str
    snapshot_values: tuple[int, ...]
    capability_names: Mapping[int, str]
    type_names: Mapping[int, MirType] | None = None

    @classmethod
    def from_values(
        cls,
        *,
        source: str,
        module_name: str,
        snapshot_values: Iterable[int],
        capability_names: Mapping[int, str],
        type_names: Mapping[int, MirType] | None = None,
    ) -> "ReplacementFunctionInput":
        return cls(
            source=source,
            module_name=module_name,
            snapshot_values=tuple(int(value) for value in snapshot_values),
            capability_names=dict(capability_names),
            type_names=None if type_names is None else dict(type_names),
        )


def _canonicalize_payloadless_enum_descriptors(snapshot):
    """Map the native no-payload sentinel to canonical MIR unit.

    Native enum catalogs use unresolved type code 0 to represent a variant with
    no payload.  Once that catalog has been emitted as an owned-enum type
    descriptor the absence is semantic, not unresolved: canonical MIR models
    the variant payload as unit.  Keep this normalization at the snapshot
    transport boundary so Python does not re-interpret source declarations.
    """

    descriptors = tuple(
        row[:3] + (_UNIT_TYPE_CODE,) + row[4:]
        if len(row) >= 4
        and row[1] == _OWNED_PAYLOAD_ENUM_DESCRIPTOR_KIND
        and row[3] == 0
        else row
        for row in snapshot.type_descriptors
    )
    if descriptors == snapshot.type_descriptors:
        return snapshot
    return replace(snapshot, type_descriptors=descriptors)


def _represent_unit_enum_storage(c_source: str) -> str:
    """Give semantic-unit enum variants inert, representable C storage.

    Canonical MIR keeps payloadless enum variants typed as ``unit``.  ``unit``
    normally emits as C ``void``, but C forbids ``void`` union fields.  Preserve
    the semantic type while assigning one byte of inert representation at the
    C storage boundary.
    """

    return _UNIT_ENUM_STORAGE.sub(r"uint8_t \1;", c_source)


def build_replacement_project_artifact(
    functions: Iterable[ReplacementFunctionInput],
    *,
    module_name: str,
) -> ReplacementBuildArtifact:
    """Assemble native-resolved functions into one canonical MIR module.

    All inputs must already contain resolved semantic/ownership/CFG decisions.
    Python performs validation and transport only. Duplicate function names are
    rejected so project assembly cannot silently replace native compiler output.
    """

    resolved = tuple(functions)
    if not resolved:
        raise ReplacementBuildError("replacement project contains no resolved functions")

    canonical_functions = []
    seen: set[str] = set()
    canonical_destructors = []
    destructors_by_target: dict[MirType, MirDestructor] = {}
    for function_input in resolved:
        snapshot = decode_resolved_source_function_snapshot(function_input.snapshot_values)
        snapshot = _canonicalize_payloadless_enum_descriptors(snapshot)
        partial = materialize_resolved_source_function_snapshot(
            source=function_input.source,
            module_name=function_input.module_name,
            snapshot=snapshot,
            capability_names=function_input.capability_names,
            type_names=function_input.type_names,
        )
        for function in partial.functions:
            if function.name in seen:
                raise ReplacementBuildError(
                    f"duplicate replacement function {function.name!r} in project assembly"
                )
            seen.add(function.name)
            canonical_functions.append(function)
        for destructor in partial.destructors:
            previous = destructors_by_target.get(destructor.target)
            if previous is not None and previous != destructor:
                raise ReplacementBuildError(
                    f"conflicting replacement destructor for {destructor.target.name!r}"
                )
            if previous is None:
                destructors_by_target[destructor.target] = destructor
                canonical_destructors.append(destructor)

    module = MirModule(
        name=module_name,
        functions=tuple(canonical_functions),
        destructors=tuple(canonical_destructors),
    )
    c_source = _represent_unit_enum_storage(emit_c_module(module))
    return ReplacementBuildArtifact(module=module, c_source=c_source)


def compile_replacement_project(
    functions: Iterable[ReplacementFunctionInput],
    output: Path,
    *,
    module_name: str,
    main_c: str = "",
    cc: str | None = None,
    c_flags: tuple[str, ...] = ("-O2",),
) -> tuple[Path, Path]:
    """Compile a project-shaped collection through canonical replacement MIR."""

    artifact = build_replacement_project_artifact(functions, module_name=module_name)
    return compile_replacement_artifact(
        artifact,
        output,
        main_c=main_c,
        cc=cc,
        c_flags=c_flags,
    )