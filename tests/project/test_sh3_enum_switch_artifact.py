"""SH3 emits the established enum-tag switch for nested payload matches."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import parse_mir
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.resolved_source_function_bundle import decode_native_project_artifact_transport
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_nested_copy_enum_switch_uses_tag(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    compiler_root = tmp_path / "compiler"
    shutil.copytree(repository / "examples/projects/bootstrap_lexer", compiler_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    manifest = compiler_root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '\n[executable]\nadapter = "stdin-string-i32"\n'
        + 'entry = "emit_native_project_artifacts"\n',
        encoding="utf-8", newline="\n",
    )
    _, _, executable = build(load_project(manifest), tmp_path / "build" / "compiler")
    source = (
        "module probe\n"
        "enum Error { A, B }\n"
        "enum Outcome { Ok(i64), Err(Error) }\n"
        "fn main()->i32 { let outcome:Outcome=Err(A()); "
        "match(outcome) { Ok(value) => { print(value); } "
        "Err(error) => { match(error) { A => { print(1); } B => { print(2); } } } } "
        "return 0; }\n"
    ).encode("utf-8")
    request = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt", (ProjectRequestUnit("src/main.mrt", source),),
        header_exports=(),
    ))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    generated = tmp_path / "nested-enum.c"
    generated.write_bytes(artifact.c_source_bytes)
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    executable_path = tmp_path / "nested-enum.exe"
    linked = subprocess.run(
        [compiler, "-std=c11", str(generated), "-o", str(executable_path)],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    run = subprocess.run([str(executable_path)], capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.replace(b"\r\n", b"\n") == b"1\n"
