from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from merit.bootstrap.native_frontend_driver import build_native_replacement_driver
from merit.compiler import CompileError
from merit.project.build import build, check
from merit.project.loader import ProjectError, load_project
from merit.project.replacement import (
    REPLACEMENT_MANIFEST,
    ReplacementProjectError,
    build_replacement_project,
)
from merit.project.replacement_prepare import (
    NativeReplacementDriver,
    prepare_replacement_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "tests" / "project" / "alpha1_corpus_v1.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _case_ids(section: str) -> list[str]:
    return [case["id"] for case in CORPUS[section]]


def _has_c_compiler() -> bool:
    configured = os.environ.get("CC")
    if configured and (shutil.which(configured) is not None or Path(configured).is_file()):
        return True
    return any(shutil.which(candidate) for candidate in ("cc", "gcc", "clang"))


def _write_project(tmp_path: Path, case: dict[str, object]) -> Path:
    root = tmp_path / str(case["id"])
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
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _run(executable: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        [str(executable)],
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _replacement_generation_bytes(project_root: Path) -> tuple[tuple[str, bytes], ...]:
    artifact_root = project_root / ".merit"
    names = [REPLACEMENT_MANIFEST]
    manifest = json.loads((artifact_root / REPLACEMENT_MANIFEST).read_text(encoding="utf-8"))
    for function in manifest["functions"]:
        names.append(function["snapshot"])
        project_source = function.get("project_source")
        if project_source is not None:
            names.append(project_source)
    return tuple(
        (name, (artifact_root / name).read_bytes())
        for name in sorted(set(names))
    )


def _reference_rejection(manifest: Path) -> tuple[str, str, str]:
    try:
        project = load_project(manifest)
    except (ProjectError, CompileError, ValueError) as exc:
        return "project-loader", type(exc).__name__, str(exc)
    try:
        check(project)
    except (ProjectError, CompileError, ValueError) as exc:
        return "reference-check", type(exc).__name__, str(exc)
    pytest.fail("reference compiler accepted an Alpha.1 rejected corpus case")


def _replacement_rejection(
    manifest: Path,
    driver: NativeReplacementDriver,
) -> tuple[str, str, str]:
    try:
        project = load_project(manifest)
    except (ProjectError, CompileError, ValueError) as exc:
        return "project-loader", type(exc).__name__, str(exc)
    try:
        prepare_replacement_artifacts(project, driver)
    except (ProjectError, CompileError, ReplacementProjectError, ValueError) as exc:
        return "replacement-prepare", type(exc).__name__, str(exc)
    pytest.fail("replacement compiler accepted an Alpha.1 rejected corpus case")


@pytest.fixture(scope="session")
def alpha1_replacement_driver(tmp_path_factory: pytest.TempPathFactory) -> NativeReplacementDriver:
    if not _has_c_compiler():
        pytest.skip("C compiler unavailable")
    output = tmp_path_factory.mktemp("alpha1-corpus-driver") / "merit-native-replacement-driver"
    return build_native_replacement_driver(output)


def test_alpha1_corpus_contract_is_complete_and_uniquely_named() -> None:
    assert CORPUS["contract"] == "alpha1-corpus-convergence-v1"
    accepted_ids = _case_ids("accepted")
    rejected_ids = _case_ids("rejected")
    all_ids = accepted_ids + rejected_ids
    assert len(all_ids) == len(set(all_ids))
    assert accepted_ids
    assert rejected_ids

    required = set(CORPUS["required_surfaces"])
    covered: set[str] = set()
    for section in ("accepted", "rejected"):
        for case in CORPUS[section]:
            assert case["files"]
            assert "src/main.mrt" in case["files"]
            covered.update(case["covers"])
    assert required <= covered


@pytest.mark.parametrize("case", CORPUS["accepted"], ids=_case_ids("accepted"))
def test_alpha1_accepted_case_converges_reference_replacement_and_native(
    tmp_path: Path,
    alpha1_replacement_driver: NativeReplacementDriver,
    case: dict[str, object],
) -> None:
    manifest = _write_project(tmp_path, case)
    project = load_project(manifest)
    check(project)

    reference_output = tmp_path / f"reference-{case['id']}"
    _, _, reference_executable = build(project, reference_output)
    reference = _run(reference_executable)
    assert reference[0] == 0, reference

    prepare_replacement_artifacts(project, alpha1_replacement_driver)
    first_generation = _replacement_generation_bytes(manifest.parent)
    prepare_replacement_artifacts(project, alpha1_replacement_driver)
    second_generation = _replacement_generation_bytes(manifest.parent)
    assert second_generation == first_generation

    replacement_output = tmp_path / f"replacement-{case['id']}"
    replacement_artifact = build_replacement_project(project, replacement_output)
    replacement = _run(replacement_artifact.executable)
    assert replacement[0] == 0, replacement
    assert replacement == reference


@pytest.mark.parametrize("case", CORPUS["rejected"], ids=_case_ids("rejected"))
def test_alpha1_rejected_case_converges_reference_and_replacement_fail_closed(
    tmp_path: Path,
    alpha1_replacement_driver: NativeReplacementDriver,
    case: dict[str, object],
) -> None:
    manifest = _write_project(tmp_path, case)

    reference_first = _reference_rejection(manifest)
    reference_second = _reference_rejection(manifest)
    assert reference_second == reference_first

    replacement_first = _replacement_rejection(manifest, alpha1_replacement_driver)
    replacement_second = _replacement_rejection(manifest, alpha1_replacement_driver)
    assert replacement_second == replacement_first

    # Project-loader rejection is shared project semantics; cases that reach the
    # native frontend must fail before publishing a replacement manifest.
    if replacement_first[0] == "replacement-prepare":
        assert not (manifest.parent / ".merit" / REPLACEMENT_MANIFEST).exists()
