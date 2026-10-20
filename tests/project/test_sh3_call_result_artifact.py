"""SH3 call results retain the canonical type and ownership contracts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.replacement_project import (
    ReplacementFunctionInput,
    build_replacement_project_artifact,
)
from merit.bootstrap.resolved_source_function_bundle import (
    decode_native_project_artifact_transport,
    decode_resolved_source_function_bundle,
)
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
@pytest.mark.parametrize(("source", "expected_output"), [
    (
        "module probe\n"
        "struct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn make()->Marker { return Marker{number:23}; }\n"
        "pub fn main()->i32 { let marker:Marker=make(); return 0; }\n",
        "23\n",
    ),
    (
        "module probe\n"
        "enum Choice { Some(i64), None }\n"
        "fn make()->Choice { return Some(7); }\n"
        "pub fn main()->i32 { let choice:Choice=make(); "
        "match(choice) { Some(value) => { print(value); } None => { print(0); } } "
        "return 0; }\n",
        "7\n",
    ),
], ids=("owned-destructor", "copy-payload-enum"))
def test_native_descriptor_backed_call_result_matches_oracle(
    tmp_path: Path, source: str, expected_output: str,
) -> None:
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
    request = encode_project_request(ProjectRequest(
        package="probe", entry="src/main.mrt",
        units=(ProjectRequestUnit(path="src/main.mrt", source=source.encode("utf-8")),),
    ))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'entry = "emit_native_project_artifacts"', 'entry = "emit_replacement_bundle"'
        ), encoding="utf-8", newline="\n",
    )
    _, _, bundle_executable = build(load_project(manifest), tmp_path / "build" / "bundle-compiler")
    bundled = subprocess.run([str(bundle_executable)], input=request, capture_output=True)
    assert bundled.returncode == 0, bundled.stderr.decode("utf-8", errors="replace")
    bundle = decode_resolved_source_function_bundle(int(line) for line in bundled.stdout.splitlines())
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
    assert artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    c_path = tmp_path / "call-result.c"
    c_path.write_bytes(artifact.c_source_bytes)
    harness = tmp_path / "harness.c"
    harness.write_text('#include "call-result.c"\nint main(void) { return merit_main(); }\n',
                       encoding="utf-8", newline="\n")
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    linked = subprocess.run([compiler, "-std=c11", str(harness), "-o", str(tmp_path / "call-result.exe")],
                            capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    executed = subprocess.run([str(tmp_path / "call-result.exe")], capture_output=True, text=True)
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout == expected_output
