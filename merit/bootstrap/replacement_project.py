"""Project-shaped entry boundary for replacement-compiler artifacts.

This module deliberately does not invoke the Python reference checker/compiler.
It packages source units with the already-resolved snapshots emitted by the
Merit-native frontend and feeds them into the canonical replacement MIR build
boundary.  It is the seam that normal project loading can target while native
multi-function/module snapshot production is completed.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    return ReplacementBuildArtifact(module=module, c_source=emit_c_module(module))


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
