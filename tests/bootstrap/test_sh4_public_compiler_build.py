"""SH4: the ordinary project command builds each usable next-stage compiler."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import encode_loaded_project_request
from merit.project.replacement_loader import load_replacement_project
from merit.bootstrap.resolved_source_function_bundle import decode_native_project_artifact_transport


ROOT = Path(__file__).resolve().parents[2]
COMPILER_SOURCE = ROOT / "examples" / "projects" / "bootstrap_lexer" / "src"
COMPILER_MANIFEST = ROOT / "compiler" / "Merit.toml"
EXPECTED_MODULES = 46


def _isolated_compiler_project(root: Path) -> Path:
    compiler = root / "compiler"
    compiler.mkdir(parents=True)
    shutil.copy2(COMPILER_MANIFEST, compiler / "Merit.toml")
    source = root / "examples" / "projects" / "bootstrap_lexer" / "src"
    shutil.copytree(COMPILER_SOURCE, source)
    assert len(tuple(source.rglob("*.mrt"))) == EXPECTED_MODULES
    assert not (compiler / ".merit").exists()
    assert not (source / ".merit").exists()
    return compiler


def _public_build(project: Path, producer: Path, output: Path) -> Path:
    project_tool = Path(sys.executable).with_name(
        "merit-project.exe" if sys.platform.startswith("win") else "merit-project"
    )
    assert project_tool.is_file(), "installed merit-project command is required"
    command = [
        str(project_tool), "build", str(project),
        "--compiler-path", str(producer), "-o", str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, (
        f"public build failed: {command!r}\n{completed.stdout}\n{completed.stderr}"
    )
    executable = output.with_suffix(".exe") if sys.platform.startswith("win") else output
    assert completed.stdout.strip() == str(executable)
    assert executable.is_file()
    return executable


def test_canonical_compiler_manifest_emits_v4_native_artifacts(tmp_path: Path) -> None:
    _, _, stage0 = build(
        load_project(COMPILER_MANIFEST), tmp_path / "stage-0" / "merit-frontend",
    )
    source = tmp_path / "probe" / "src" / "main.mrt"
    source.parent.mkdir(parents=True)
    source.write_text("module main\nfn main()->i32 { return 0; }\n", encoding="utf-8")
    (source.parent.parent / "Merit.toml").write_text(
        '[package]\nname="probe"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n', encoding="utf-8",
    )
    request = encode_loaded_project_request(
        load_replacement_project(source.parent.parent / "Merit.toml"),
        header_exports=frozenset(),
    )
    completed = subprocess.run([str(stage0)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    transport = decode_native_project_artifact_transport(
        tuple(int(value) for value in completed.stdout.splitlines())
    )
    assert transport.canonical_mir_bytes
    assert transport.c_source_bytes
    assert transport.c_header_bytes


def test_public_command_builds_usable_next_stage_from_complete_source(
    tmp_path: Path,
) -> None:
    _, _, stage0 = build(
        load_project(COMPILER_MANIFEST), tmp_path / "stage-0" / "merit-frontend",
    )
    stage1_project = _isolated_compiler_project(tmp_path / "stage-1-source")
    stage2_project = _isolated_compiler_project(tmp_path / "stage-2-source")

    stage1 = _public_build(
        stage1_project, stage0, tmp_path / "stage-1" / "merit-frontend",
    )
    stage2 = _public_build(
        stage2_project, stage1, tmp_path / "stage-2" / "merit-frontend",
    )
    assert stage2.is_file()
