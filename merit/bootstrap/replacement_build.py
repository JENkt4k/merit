"""First-class build boundary for the Merit-native replacement compiler.

The native bootstrap pipeline owns semantic resolution and emits a versioned
resolved-source-function snapshot.  This module is the production-side handoff:
it validates/materializes that snapshot as canonical bootstrap MIR, emits C only
from that MIR, and can compile the result with a host C11 compiler.

No source parsing, HIR lowering, ownership inference, CFG inference, contract
inference, or capability inference is permitted here.  Python remains an
independent adapter/oracle until the native compiler can materialize canonical
MIR directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Iterable, Mapping

from merit.bootstrap.mir_contract import MirModule, MirType
from merit.bootstrap.mir_to_c import emit_c_module
from merit.bootstrap.resolved_source_function_snapshot import (
    decode_resolved_source_function_snapshot,
    materialize_resolved_source_function_snapshot,
)


class ReplacementBuildError(RuntimeError):
    """Raised when a canonical replacement build cannot be completed."""


@dataclass(frozen=True)
class ReplacementBuildArtifact:
    """Canonical artifacts produced from already-resolved native records."""

    module: MirModule
    c_source: str


def build_replacement_artifact(
    *,
    source: str,
    module_name: str,
    snapshot_values: Iterable[int],
    capability_names: Mapping[int, str],
    type_names: Mapping[int, MirType] | None = None,
) -> ReplacementBuildArtifact:
    """Build canonical MIR and deterministic C from a native snapshot.

    This is intentionally the narrow replacement-compiler production boundary:
    callers provide the source only for source-span/provenance reconstruction;
    every semantic decision must already be represented by ``snapshot_values``.
    """

    snapshot = decode_resolved_source_function_snapshot(snapshot_values)
    module = materialize_resolved_source_function_snapshot(
        source=source,
        module_name=module_name,
        snapshot=snapshot,
        capability_names=capability_names,
        type_names=type_names,
    )
    return ReplacementBuildArtifact(module=module, c_source=emit_c_module(module))


def compile_replacement_artifact(
    artifact: ReplacementBuildArtifact,
    output: Path,
    *,
    main_c: str = "",
    cc: str | None = None,
    c_flags: tuple[str, ...] = ("-O2",),
) -> tuple[Path, Path]:
    """Compile deterministic C emitted from canonical replacement MIR.

    Returns ``(c_path, executable_path)``.  The optional ``main_c`` is a foreign
    C harness only; it cannot alter the canonical Merit function bodies.
    """

    compiler = cc or next(
        (candidate for candidate in ("cc", "gcc", "clang") if shutil.which(candidate)),
        None,
    )
    if compiler is None:
        raise ReplacementBuildError(
            "no C compiler found for replacement build; install GCC/Clang or pass cc="
        )

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    executable = output.with_suffix(".exe") if __import__("os").name == "nt" else output
    c_path = output.with_suffix(".c")
    c_source = artifact.c_source
    if main_c:
        c_source += "\n" + main_c.rstrip() + "\n"
    c_path.write_text(c_source, encoding="utf-8", newline="\n")

    command = [compiler, "-std=c11", "-Wall", "-Wextra", *c_flags, str(c_path), "-o", str(executable)]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown compiler failure"
        raise ReplacementBuildError(f"replacement C compilation failed: {detail}")
    return c_path, executable
