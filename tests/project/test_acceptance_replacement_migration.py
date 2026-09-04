from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from merit.bootstrap.native_frontend_driver import build_native_replacement_driver
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.replacement import REPLACEMENT_MANIFEST, build_replacement_project
from merit.project.replacement_prepare import NativeReplacementDriver, prepare_replacement_artifacts
from scripts.m7_acceptance_inventory import ACCEPTANCE_PROJECTS


ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ROOT / "examples" / "projects"
EXECUTABLE_TIMEOUT_SECONDS = 30


def _has_c_compiler() -> bool:
    configured = os.environ.get("CC")
    if configured and (shutil.which(configured) is not None or Path(configured).is_file()):
        return True
    return any(shutil.which(candidate) for candidate in ("cc", "gcc", "clang"))


def _run(executable: Path, cwd: Path) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            [str(executable)],
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            check=False,
            timeout=EXECUTABLE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"acceptance executable timed out after {EXECUTABLE_TIMEOUT_SECONDS}s: {executable}"
        ) from exc
    return completed.returncode, completed.stdout, completed.stderr


def _generation_bytes(project_root: Path) -> tuple[tuple[str, bytes], ...]:
    artifact_root = project_root / ".merit"
    manifest_path = artifact_root / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = [REPLACEMENT_MANIFEST]
    for function in manifest["functions"]:
        names.append(function["snapshot"])
        project_source = function.get("project_source")
        if project_source is not None:
            names.append(project_source)
    return tuple(
        (name, (artifact_root / name).read_bytes())
        for name in sorted(set(names))
    )


def _observable_tree(root: Path) -> tuple[tuple[str, bytes], ...]:
    ignored_parts = {".merit", "build", ".merit-cache", "__pycache__"}
    rows: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in ignored_parts for part in relative.parts):
            continue
        if path.suffix.lower() in {".o", ".obj", ".exe", ".dll", ".so", ".dylib"}:
            continue
        rows.append((relative.as_posix(), path.read_bytes()))
    return tuple(rows)


def _copy_project(tmp_path: Path, name: str, variant: str) -> Path:
    destination = tmp_path / f"{name}-{variant}"
    shutil.copytree(PROJECTS / name, destination, ignore=shutil.ignore_patterns("build", ".merit", ".merit-cache", "__pycache__"))
    return destination


@pytest.fixture(scope="session")
def acceptance_replacement_driver(tmp_path_factory: pytest.TempPathFactory) -> NativeReplacementDriver:
    if not _has_c_compiler():
        pytest.skip("C compiler unavailable")
    output = tmp_path_factory.mktemp("m7-acceptance-driver") / "merit-native-replacement-driver"
    return build_native_replacement_driver(output)


def test_m7_acceptance_inventory_is_exact() -> None:
    assert len(ACCEPTANCE_PROJECTS) == 10
    assert len(set(ACCEPTANCE_PROJECTS)) == 10
    assert "ledger_app" in ACCEPTANCE_PROJECTS
    for name in ACCEPTANCE_PROJECTS:
        assert (PROJECTS / name / "Merit.toml").is_file(), name


@pytest.mark.parametrize("name", ACCEPTANCE_PROJECTS)
def test_acceptance_project_converges_through_replacement(
    tmp_path: Path,
    acceptance_replacement_driver: NativeReplacementDriver,
    name: str,
) -> None:
    reference_root = _copy_project(tmp_path, name, "reference")
    replacement_root = _copy_project(tmp_path, name, "replacement")

    reference_project = load_project(reference_root / "Merit.toml")
    replacement_project = load_project(replacement_root / "Merit.toml")

    _, _, reference_executable = build(reference_project, tmp_path / f"reference-{name}")
    reference = _run(reference_executable, reference_root)
    assert reference[0] == 0, (name, reference)
    reference_tree = _observable_tree(reference_root)

    prepare_replacement_artifacts(replacement_project, acceptance_replacement_driver)
    first_generation = _generation_bytes(replacement_root)
    prepare_replacement_artifacts(replacement_project, acceptance_replacement_driver)
    second_generation = _generation_bytes(replacement_root)
    assert second_generation == first_generation, name

    replacement_artifact = build_replacement_project(
        replacement_project,
        tmp_path / f"replacement-{name}",
    )
    replacement = _run(replacement_artifact.executable, replacement_root)
    assert replacement[0] == 0, (name, replacement)
    replacement_tree = _observable_tree(replacement_root)

    assert replacement == reference, name
    assert replacement_tree == reference_tree, name
