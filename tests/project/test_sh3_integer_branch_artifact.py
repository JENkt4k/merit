"""SH3 preserves Alpha.2 i32 truthy branch conditions in canonical C."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import MirType, parse_mir
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.resolved_source_function_bundle import decode_native_project_artifact_transport
from merit.compiler import Checker, parse
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_i32_branch_matches_reference_semantics(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    source = (
        "module branch_probe\n"
        "fn main()->i32 { let flag:i32=1; if (flag) { print(7); } "
        "else { print(8); } return 0; }\n"
    )
    Checker(parse(source)).check()
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
    _, _, compiler = build(load_project(manifest), tmp_path / "compiler-build")
    request = encode_project_request(ProjectRequest(
        "branch_probe", "src/main.mrt",
        (ProjectRequestUnit("src/main.mrt", source.encode("utf-8")),), header_exports=(),
    ))
    response = subprocess.run([str(compiler)], input=request, capture_output=True)
    assert response.returncode == 0, response.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in response.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    function = next(function for function in module.functions if function.name == "main")
    local_types = {local.local_id: local.type for local in function.locals}
    conditions = [block.terminator.operands[0] for block in function.blocks
                  if block.terminator.kind == "branch"]
    assert conditions
    assert any(local_types[condition] == MirType("i32") for condition in conditions)
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        module, exported_names=frozenset()
    )
    generated = tmp_path / "branch.c"
    generated.write_bytes(artifact.c_source_bytes)
    c_compiler = shutil.which("cc") or shutil.which("gcc")
    assert c_compiler is not None
    executable = tmp_path / "branch.exe"
    linked = subprocess.run([c_compiler, "-std=c11", str(generated), "-o", str(executable)],
                            capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    native_run = subprocess.run([str(executable)], capture_output=True)
    assert native_run.returncode == 0
    assert native_run.stdout.splitlines() == [b"7"]
