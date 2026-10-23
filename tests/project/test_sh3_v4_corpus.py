"""Run fixed corpus and acceptance projects through the SH3 native-v4 path."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from merit.compiler import CompileError
from merit.project.build import build, check
from merit.project.cli import main as project_cli_main
from merit.project.loader import ProjectError, load_project
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request
from merit.project.replacement import (
    REPLACEMENT_MANIFEST, ReplacementProjectError, build_replacement_project,
    build_replacement_shared,
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


def _result(executable: Path, *, cwd: Path | None = None) -> tuple[int, bytes, bytes]:
    completed = subprocess.run([str(executable)], cwd=cwd, capture_output=True, timeout=30)
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
        assert case["id"] in {
            "wrong-generic-arity", "missing-trait-implementation",
            "private-qualified-call", "unimported-qualified-call",
        }
        units = tuple(
            ProjectRequestUnit(path, str(source).encode("utf-8"))
            for path, source in sorted(dict(case["files"]).items())
        )
        request = encode_project_request(ProjectRequest(
            manifest.parent.name.replace("-", "_"), "src/main.mrt", units,
            header_exports=(),
        ))
        response = subprocess.run(
            [str(native_v4_driver.executable)], input=request, capture_output=True,
        )
        assert response.returncode != 0, case["id"]
        assert b"replacement driver status" in response.stderr
        return
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


def test_sh3_v4_rejects_missing_import_without_python_loader(
    native_v4_driver: NativeReplacementDriver,
) -> None:
    request = encode_project_request(ProjectRequest(
        "missing_import", "src/main.mrt",
        (ProjectRequestUnit(
            "src/main.mrt",
            b"module main\nimport absent;\nfn main()->i32 { return 0; }\n",
        ),), header_exports=(),
    ))
    response = subprocess.run(
        [str(native_v4_driver.executable)], input=request, capture_output=True,
    )
    assert response.returncode != 0
    assert b"replacement driver status" in response.stderr


@pytest.mark.parametrize("name, side_effect", [
    ("binary_packet", None),
    ("borrowed_views", None),
    ("cobol_finance_modernization", None),
    ("filesystem_capabilities", "merit-filesystem-capabilities.bin"),
    ("generic_collections", None),
    ("generic_result", None),
    ("ledger_app", "ledger_report.txt"),
    ("text_pipeline", None),
    ("trait_bounds", None),
])
def test_sh3_v4_acceptance_project_builds_through_production_path(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
    name: str, side_effect: str | None,
) -> None:
    project_root = tmp_path / name
    shutil.copytree(ROOT / "examples/projects" / name, project_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    project = load_project(project_root / "Merit.toml")
    _, _, reference = build(project, tmp_path / "reference")
    native_output = tmp_path / "native-v4"
    assert project_cli_main([
        "build", str(project_root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(native_output),
    ]) == 0
    manifest = json.loads((project_root / ".merit" / REPLACEMENT_MANIFEST).read_text(
        encoding="utf-8"
    ))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v2/resolved-source-function-bundle-v4"
    )
    assert set(manifest["native_artifacts"]) == {"canonical_mir", "c_source", "c_header"}
    native_executable = native_output.with_suffix(".exe") if os.name == "nt" else native_output

    reference_directory = tmp_path / "reference-run"
    native_directory = tmp_path / "native-run"
    reference_directory.mkdir()
    native_directory.mkdir()
    expected = _result(reference, cwd=reference_directory)
    actual = _result(native_executable, cwd=native_directory)
    assert expected[0] == 0, expected
    assert actual == expected
    if side_effect is not None:
        assert (native_directory / side_effect).read_bytes() == (
            reference_directory / side_effect
        ).read_bytes()


def test_sh3_v4_public_check_shared_and_run_keep_explicit_empty_exports(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    project_root = tmp_path / "generic_result"
    shutil.copytree(ROOT / "examples/projects/generic_result", project_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    driver = str(native_v4_driver.executable)
    assert project_cli_main(["check", str(project_root), "--compiler-path", driver]) == 0
    assert project_cli_main([
        "build-shared", str(project_root), "--compiler-path", driver,
        "-o", str(tmp_path / "native-shared"),
    ]) == 0
    assert project_cli_main([
        "run", str(project_root), "--compiler-path", driver,
        "-o", str(tmp_path / "native-run"),
    ]) == 0
    manifest = json.loads((project_root / ".merit" / REPLACEMENT_MANIFEST).read_text(
        encoding="utf-8"
    ))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v2/resolved-source-function-bundle-v4"
    )


def test_sh3_v4_public_shared_build_selects_only_manifest_entry(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "selected"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="selected"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n\n'
        '[executable]\nadapter="stdin-string-i32"\nentry="selected"\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module selected\n'
        'pub fn selected(source:String)->i32 { return 0; }\n'
        'pub fn omitted()->i32 { return 1; }\n',
        encoding="utf-8", newline="\n",
    )
    output = tmp_path / "selected-library"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_text(encoding="utf-8")
    assert "merit_selected" in header
    assert "merit_omitted" not in header
    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    library = ctypes.CDLL(str(output.with_suffix(suffix)))

    class MeritString(ctypes.Structure):
        _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("len", ctypes.c_size_t)]

    selected = library.merit_selected
    selected.argtypes = [MeritString]
    selected.restype = ctypes.c_int32
    text = (ctypes.c_uint8 * 3)(97, 98, 99)
    assert selected(MeritString(text, 3)) == 0
    manifest = json.loads((root / ".merit" / REPLACEMENT_MANIFEST).read_text(
        encoding="utf-8"
    ))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v2/resolved-source-function-bundle-v4"
    )


@pytest.mark.parametrize("entry", ["private_entry", "missing_entry"])
def test_sh3_v4_public_shared_build_rejects_unexportable_entry(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, entry: str,
) -> None:
    root = tmp_path / entry
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="unexportable"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n\n'
        f'[executable]\nadapter="stdin-string-i32"\nentry="{entry}"\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module unexportable\n'
        'fn private_entry(source:String)->i32 { return 0; }\n'
        'pub fn available(source:String)->i32 { return 1; }\n',
        encoding="utf-8", newline="\n",
    )
    output = tmp_path / "unexportable-library"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) != 0
    assert not (root / ".merit" / REPLACEMENT_MANIFEST).exists()
    assert not output.with_suffix(".h").exists()


def test_sh3_v4_public_shared_build_preserves_stable_struct_abi(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "shared_struct_api"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="shared_struct_api"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module shared_struct_api\n'
        'pub stable("point-v1") struct Point { x:i32; y:i32; }\n'
        'pub fn point_sum(point:Point)->i32 { return checked_add(point.x,point.y); }\n'
        'fn main()->i32 { return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    assert project_cli_main([
        "build", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(tmp_path / "plain-executable"),
    ]) == 0
    with pytest.raises(ReplacementProjectError, match="missing or incompatible"):
        build_replacement_shared(
            load_project(root / "Merit.toml"), tmp_path / "stale-empty-header",
        )
    output = tmp_path / "shared_struct_api"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_text(encoding="utf-8")
    assert "merit_point_sum" in header
    assert "sizeof(merit_Point) == 8" in header
    manifest = json.loads((root / ".merit" / REPLACEMENT_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v1/resolved-source-function-bundle-v4"
    )

    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]

    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    library = ctypes.CDLL(str(output.with_suffix(suffix)))
    point_sum = library.merit_point_sum
    point_sum.argtypes = [Point]
    point_sum.restype = ctypes.c_int32
    assert point_sum(Point(19, 23)) == 42
