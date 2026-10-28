"""SH3 vector/aggregate C names match the source-backed MIR type identity."""

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
from merit.project.project_request import encode_loaded_project_request
from merit.project.replacement_loader import load_replacement_project


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_generic_collections_vector_aggregate_artifact(tmp_path: Path) -> None:
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
    project = load_replacement_project(
        repository / "examples/projects/generic_collections/Merit.toml"
    )
    request = encode_loaded_project_request(project, header_exports=frozenset())
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        module, exported_names=frozenset()
    )
    source = tmp_path / "generic-collections.c"
    source.write_bytes(artifact.c_source_bytes)
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    linked = subprocess.run(
        [compiler, "-std=c11", str(source), "-o", str(tmp_path / "generic-collections.exe")],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    reference_project = load_project(repository / "examples/projects/generic_collections/Merit.toml")
    _, _, reference_executable = build(reference_project, tmp_path / "build" / "reference-generic-collections")
    reference_run = subprocess.run([str(reference_executable)], capture_output=True)
    native_run = subprocess.run([str(tmp_path / "generic-collections.exe")], capture_output=True)
    assert reference_run.returncode == 0, reference_run.stderr
    assert native_run.returncode == reference_run.returncode, native_run.stderr
    assert native_run.stdout == reference_run.stdout
