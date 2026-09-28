from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from merit.project.build import build
from merit.project.loader import load_project
from merit.project.manifest import load_manifest


def _adapter_project(root: Path, *, status: int = 0) -> Path:
    (root / "src").mkdir(parents=True)
    manifest = root / "Merit.toml"
    manifest.write_text(
        '[package]\nname = "adapter_project"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n\n'
        '[executable]\nadapter = "stdin-string-i32"\nentry = "consume"\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(
        "module adapter_project\n"
        f"pub fn consume(source_text:String)->i32 {{ return {status}; }}\n"
        "fn main()->i32 { return 99; }\n",
        encoding="utf-8",
    )
    return manifest


def test_compiler_manifest_uses_complete_source_closure_and_generic_adapter() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = load_manifest(root / "compiler" / "Merit.toml")
    assert manifest.name == "bootstrap_compiler"
    assert manifest.executable_adapter == "stdin-string-i32"
    assert manifest.executable_entry == "emit_replacement_bundle"
    sources = {
        path.resolve()
        for pattern in manifest.sources
        for path in manifest.root.glob(pattern)
        if path.is_file()
    }
    assert len(sources) == 45


@pytest.mark.skipif(
    shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None,
    reason="C compiler unavailable",
)
def test_reference_project_build_links_generic_stdin_string_i32_adapter(tmp_path: Path) -> None:
    project = load_project(_adapter_project(tmp_path / "adapter", status=23))
    _, _, executable = build(project, tmp_path / "out" / "adapter")
    completed = subprocess.run(
        [str(executable)], input=b"arbitrary bytes\x00remain transport", capture_output=True,
    )
    assert completed.returncode == 23
    assert completed.stdout == b""
    assert completed.stderr.splitlines() == [b"replacement driver status 23"]


@pytest.mark.parametrize(
    "executable, message",
    [
        ('adapter = "unknown"\nentry = "consume"\n', "executable.adapter"),
        ('adapter = "stdin-string-i32"\nentry = "not-valid!"\n', "executable.entry"),
        ('adapter = "stdin-string-i32"\n', "executable.entry"),
    ],
)
def test_manifest_rejects_invalid_executable_adapter_contract(
    tmp_path: Path, executable: str, message: str,
) -> None:
    manifest = tmp_path / "Merit.toml"
    manifest.write_text(
        '[package]\nname = "invalid"\nentry = "src/main.mrt"\n\n'
        f"[executable]\n{executable}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_manifest(manifest)
