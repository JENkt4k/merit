"""SH3 proves explicit owned moves at every reachable return block."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.replacement_project import ReplacementFunctionInput, build_replacement_project_artifact
from merit.bootstrap.resolved_source_function_bundle import (
    decode_native_project_artifact_transport,
    decode_resolved_source_function_bundle,
)
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import (
    ProjectRequest, ProjectRequestUnit, encode_loaded_project_request, encode_project_request,
)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_multiblock_owned_return_matches_oracle(tmp_path: Path) -> None:
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
    _, _, compiler = build(load_project(manifest), tmp_path / "build" / "compiler")
    source = (
        "module probe\n"
        "struct Receipt { value:i64; other:i64; }\n"
        "enum Choice { HasBuffer(Buffer), Empty(Receipt) }\n"
        "fn choose(selector:i64)->Choice {\n"
        "    if (selector > 0) { return Empty(Receipt { value:1, other:3 }); }\n"
        "    else { return Empty(Receipt { value:2, other:4 }); }\n"
        "}\n"
        "fn main()->i32 { return 0; }\n"
    ).encode("utf-8")
    request = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt", (ProjectRequestUnit("src/main.mrt", source),),
        header_exports=(),
    ))
    completed = subprocess.run([str(compiler)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    selected = next(function for function in module.functions if function.name == "choose")
    assert len(selected.blocks) > 1
    assert sum(block.terminator.kind == "return" for block in selected.blocks) >= 2
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        module, exported_names=frozenset()
    )
    generated = tmp_path / "multiblock-owned-return.c"
    generated.write_bytes(artifact.c_source_bytes)
    c_compiler = shutil.which("cc") or shutil.which("gcc")
    assert c_compiler is not None
    executable = tmp_path / "multiblock-owned-return.exe"
    linked = subprocess.run(
        [c_compiler, "-std=c11", str(generated), "-o", str(executable)],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    run = subprocess.run([str(executable)], capture_output=True)
    assert run.returncode == 0, run.stderr

    finance = load_project(repository / "examples/projects/cobol_finance_modernization/Merit.toml")
    finance_request = encode_loaded_project_request(finance, header_exports=())
    finance_completed = subprocess.run(
        [str(compiler)], input=finance_request, capture_output=True,
    )
    assert finance_completed.returncode == 0, finance_completed.stderr.decode(
        "utf-8", errors="replace"
    )
    finance_artifact = decode_native_project_artifact_transport(
        int(line) for line in finance_completed.stdout.splitlines()
    )
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'entry = "emit_native_project_artifacts"', 'entry = "emit_replacement_bundle"'
        ), encoding="utf-8", newline="\n",
    )
    _, _, legacy_compiler = build(load_project(manifest), tmp_path / "build" / "legacy-compiler")
    legacy_completed = subprocess.run(
        [str(legacy_compiler)], input=finance_request, capture_output=True,
    )
    assert legacy_completed.returncode == 0, legacy_completed.stderr.decode(
        "utf-8", errors="replace"
    )
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in legacy_completed.stdout.splitlines()
    )
    oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=bytes(bundle.functions[0].effective_source_bytes).decode("utf-8"),
                module_name=bundle.module_name,
                snapshot_values=values,
                capability_names={index + 1: name for index, name in enumerate(bundle.capability_names)},
            )
            for values in bundle.encoded_snapshots
        ), module_name=bundle.module_name,
    )
    assert finance_artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    finance_module = parse_mir(json.loads(finance_artifact.canonical_mir_bytes))
    assert finance_artifact.c_source_bytes.decode("utf-8") == emit_c_module(finance_module)
    assert finance_artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        finance_module, exported_names=frozenset()
    )
    finance_c = tmp_path / "finance-native.c"
    finance_c.write_bytes(finance_artifact.c_source_bytes)
    finance_executable = tmp_path / "finance-native.exe"
    finance_linked = subprocess.run(
        [c_compiler, "-std=c11", str(finance_c), "-o", str(finance_executable)],
        capture_output=True, text=True,
    )
    assert finance_linked.returncode == 0, finance_linked.stderr
    _, _, finance_reference_executable = build(finance, tmp_path / "finance-reference")
    reference_run = subprocess.run([str(finance_reference_executable)], capture_output=True)
    native_run = subprocess.run([str(finance_executable)], capture_output=True)
    assert reference_run.returncode == 0, reference_run.stderr
    assert native_run.returncode == 0, native_run.stderr
    assert native_run.stdout == reference_run.stdout
