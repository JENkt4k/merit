"""Run the fixed Alpha.1 convergence corpus through the SH3 native-v4 path."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from merit.compiler import CompileError
from merit.project.build import build, check
from merit.project.loader import ProjectError, load_project
from merit.project.replacement import (
    REPLACEMENT_MANIFEST, ReplacementProjectError, build_replacement_project,
)
from merit.project.replacement_prepare import NativeReplacementDriver, prepare_replacement_artifacts


ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads((ROOT / "tests/project/alpha1_corpus_v1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native_v4_driver(tmp_path_factory: pytest.TempPathFactory) -> NativeReplacementDriver:
    if not any(shutil.which(name) for name in ("cc", "gcc", "clang")):
        pytest.skip("C compiler unavailable")

    temporary = tmp_path_factory.mktemp("sh3-v4-corpus-compiler")
    compiler_root = temporary / "compiler"
    shutil.copytree(ROOT / "examples/projects/bootstrap_lexer", compiler_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    manifest = compiler_root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '\n[executable]\nadapter = "stdin-string-i32"\n'
        + 'entry = "emit_native_project_artifacts"\n',
        encoding="utf-8", newline="\n",
    )
    _, _, executable = build(load_project(manifest), temporary / "native-v4-compiler")
    return NativeReplacementDriver(executable)


def _write_case(root: Path, case: dict[str, object]) -> Path:
    root.mkdir()
    for relative, source in dict(case["files"]).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(source), encoding="utf-8", newline="\n")
    manifest = root / "Merit.toml"
    manifest.write_text(
        '[package]\n'
        f'name="alpha1_{str(case["id"]).replace("-", "_")}"\n'
        'entry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    return manifest


def _result(executable: Path) -> tuple[int, bytes, bytes]:
    completed = subprocess.run([str(executable)], capture_output=True, timeout=30)
    return completed.returncode, completed.stdout, completed.stderr


@pytest.mark.parametrize("case", CORPUS["accepted"], ids=lambda case: case["id"])
def test_sh3_v4_accepts_complete_alpha1_corpus(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, case: dict[str, object],
) -> None:
    manifest = _write_case(tmp_path / str(case["id"]), case)
    project = load_project(manifest)
    check(project)
    _, _, reference = build(project, tmp_path / "reference")
    expected = _result(reference)
    assert expected[0] == 0, expected

    prepared = prepare_replacement_artifacts(project, native_v4_driver)
    assert len(prepared.project_artifact_paths) == 3
    first_publication = (
        prepared.manifest_path.read_bytes(),
        tuple(path.read_bytes() for path in prepared.project_artifact_paths),
    )
    repeated = prepare_replacement_artifacts(project, native_v4_driver)
    assert (
        repeated.manifest_path.read_bytes(),
        tuple(path.read_bytes() for path in repeated.project_artifact_paths),
    ) == first_publication
    artifact = build_replacement_project(project, tmp_path / "native-v4")
    assert _result(artifact.executable) == expected


@pytest.mark.parametrize("case", CORPUS["rejected"], ids=lambda case: case["id"])
def test_sh3_v4_rejects_complete_alpha1_corpus(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, case: dict[str, object],
) -> None:
    manifest = _write_case(tmp_path / str(case["id"]), case)
    try:
        project = load_project(manifest)
    except (ProjectError, CompileError, ValueError):
        return  # Shared project loader rejects before either compiler stage.
    with pytest.raises((ProjectError, CompileError, ValueError)):
        check(project)

    def rejection() -> tuple[str, str, str]:
        try:
            prepare_replacement_artifacts(project, native_v4_driver)
        except (ProjectError, CompileError, ReplacementProjectError, ValueError) as exc:
            assert not (manifest.parent / ".merit" / REPLACEMENT_MANIFEST).exists()
            return "prepare", type(exc).__name__, str(exc)
        try:
            build_replacement_project(project, tmp_path / "rejected-v4")
        except (ProjectError, CompileError, ReplacementProjectError, ValueError) as exc:
            return "build", type(exc).__name__, str(exc)
        pytest.fail("native-v4 compiler accepted a rejected Alpha.1 corpus case")

    first = rejection()
    assert first[0] == "prepare", (case["id"], first)
    assert rejection() == first
