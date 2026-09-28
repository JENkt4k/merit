"""Build the concrete Merit-native replacement frontend driver.

The resulting artifact is a native executable. A tiny C host owns only process
I/O: it reads stdin into the stable public ``merit_String`` ABI and calls the
single exported Merit frontend entrypoint. Target-source lexing and semantic
lowering remain in Merit code; the host does not inspect or reinterpret source
text.

The host intentionally does not include the generated whole-project header. The
bootstrap project contains private compiler implementation structs whose public
header ordering is not part of this driver boundary. Mirroring only the stable
``String`` representation plus the one exported function keeps the process shim
coupled to the ABI it actually consumes instead of the bootstrap compiler's
internal generated types.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from merit.project.build import build, build_shared
from merit.project.executable_adapter import (
    STDIN_STRING_I32_ADAPTER,
    link_executable_adapter,
)
from merit.project.loader import load_project
from merit.project.replacement import build_replacement_shared
from merit.project.replacement_loader import load_replacement_project
from merit.project.replacement_prepare import NativeReplacementDriver
from merit.project.replacement_prepare import prepare_replacement_artifacts


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_PROJECT = ROOT / "examples" / "projects" / "bootstrap_lexer" / "Merit.toml"
COMPILER_PROJECT = ROOT / "compiler" / "Merit.toml"
REPLACEMENT_FRONTEND_ENTRYPOINT = "emit_replacement_bundle"


@dataclass(frozen=True)
class ReplacementCompilerStage:
    """Canonical and native artifacts for one replacement compiler stage."""

    driver: NativeReplacementDriver
    c_path: Path
    header_path: Path
    library: Path


def _link_native_replacement_driver(output: Path, library: Path) -> NativeReplacementDriver:
    executable = link_executable_adapter(
        output,
        library=library,
        adapter=STDIN_STRING_I32_ADAPTER,
        entry=REPLACEMENT_FRONTEND_ENTRYPOINT,
    )
    return NativeReplacementDriver(executable)


def build_native_replacement_driver(output: Path) -> NativeReplacementDriver:
    """Build the stage-0 Python-reference-produced frontend driver."""

    output = output.expanduser().resolve()
    project = load_project(COMPILER_PROJECT)
    _, _, executable = build(project, output)
    return NativeReplacementDriver(executable)


def _copy_isolated_compiler_source(destination: Path) -> None:
    shutil.copytree(
        BOOTSTRAP_PROJECT.parent,
        destination,
        ignore=shutil.ignore_patterns(".merit", "build", "__pycache__", "*.pyc"),
    )


def build_replacement_compiler_stage(
    output: Path,
    producer: NativeReplacementDriver,
) -> ReplacementCompilerStage:
    """Use ``producer`` to compile an isolated next-stage frontend driver."""

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="merit-compiler-stage-") as temporary:
        isolated_root = Path(temporary) / "bootstrap_lexer"
        _copy_isolated_compiler_source(isolated_root)
        project = load_replacement_project(isolated_root / "Merit.toml")
        prepare_replacement_artifacts(project, producer)
        shared = build_replacement_shared(
            project,
            output.parent / f"{output.stem}-frontend",
            header_exports=frozenset({REPLACEMENT_FRONTEND_ENTRYPOINT}),
        )
    driver = _link_native_replacement_driver(output, shared.library)
    return ReplacementCompilerStage(
        driver=driver,
        c_path=shared.c_path,
        header_path=shared.header_path,
        library=shared.library,
    )
