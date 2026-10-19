"""SH3 regression: native project artifacts retain explicit destructors."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import parse_mir
from merit.bootstrap.mir_to_c import _destructor_c_name, _type, emit_c_header, emit_c_module
from merit.bootstrap.resolved_source_function_snapshot import decode_resolved_source_function_snapshot
from merit.bootstrap.resolved_source_function_bundle import (
    decode_native_project_artifact_transport,
    decode_resolved_source_function_bundle,
)
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import (
    ProjectRequest,
    ProjectRequestUnit,
    encode_loaded_project_request,
    encode_project_request,
)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
@pytest.mark.parametrize(("fields", "main_source", "expected_output"), [
    ("number:i64;", "return 0;", "23\n"),
    ("number:i64; other:i64;", "return 0;", "23\n"),
    ("number:i64;", "let marker:Marker=Marker{number:23}; return 0;", "23\n"),
    ("number:i64;", "let marker:Marker=Marker{number:23}; drop(marker); return 0;", "23\n"),
    ("number:i64; other:i64;", "let marker:Marker=Marker{number:23,other:5}; return 0;", "23\n"),
    ("number:i64; other:i64;", "let marker:Marker=Marker{number:23,other:5}; drop(marker); return 0;", "23\n"),
])
def test_native_v4_artifact_retains_destructor_mir_and_c(
    tmp_path: Path, fields: str, main_source: str, expected_output: str,
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

    source_root = tmp_path / "input"
    (source_root / "src").mkdir(parents=True)
    (source_root / "Merit.toml").write_text(
        '[package]\nname = "probe"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n', encoding="utf-8", newline="\n",
    )
    source_path = source_root / "src/main.mrt"
    source_path.write_text(
        "module probe\n"
        f"struct Marker {{ {fields} }}\n"
        "pub fn main()->i32 { return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    baseline_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    baseline = subprocess.run([str(executable)], input=baseline_request, capture_output=True)
    assert baseline.returncode == 0, baseline.stderr.decode("utf-8", errors="replace")
    source_path.write_text(
        "module probe\n"
        f"struct Marker {{ {fields} }}\n"
        "destructor Marker { print(self.number); }\n"
        f"pub fn main()->i32 {{ {main_source} }}\n",
        encoding="utf-8", newline="\n",
    )
    request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'entry = "emit_native_project_artifacts"', 'entry = "emit_replacement_bundle"'
        ), encoding="utf-8", newline="\n",
    )
    _, _, bundle_executable = build(load_project(manifest), tmp_path / "build" / "bundle-compiler")
    bundle_baseline = subprocess.run([str(bundle_executable)], input=baseline_request, capture_output=True)
    assert bundle_baseline.returncode == 0, bundle_baseline.stderr.decode("utf-8", errors="replace")
    assert bundle_baseline.stdout.splitlines()[:2] == [b"1297236550", b"3"]
    bundle_completed = subprocess.run([str(bundle_executable)], input=request, capture_output=True)
    assert bundle_completed.returncode == 0, bundle_completed.stderr.decode("utf-8", errors="replace")
    bundle_values = [int(line) for line in bundle_completed.stdout.splitlines()]
    partial_snapshot = decode_resolved_source_function_snapshot(
        bundle_values[4:4 + bundle_values[3]]
    )
    assert bundle_completed.returncode == 0, (
        bundle_completed.stderr.decode("utf-8", errors="replace"),
        partial_snapshot.destructors,
    )
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in bundle_completed.stdout.splitlines()
    )
    assert len(bundle.functions) == 1
    assert len(bundle.functions[0].body_records) >= 2
    assert len(bundle.functions[0].destructors) == 1
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    canonical = json.loads(artifact.canonical_mir_bytes)
    assert len(canonical["destructors"]) == 1
    module = parse_mir(canonical)
    assert module.destructors[0].target.name.startswith(
        "struct_i64_destructor_" if fields == "number:i64;" else "struct_aggregate_"
    )
    assert module.destructors[0].locals[0].name == "self"
    assert module.destructors[0].locals[0].ownership == "mutable_borrow"
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    c_path = tmp_path / "destructor-artifact.c"
    c_path.write_bytes(artifact.c_source_bytes)
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    compiled = subprocess.run(
        [compiler, "-std=c11", "-c", str(c_path), "-o", str(tmp_path / "destructor-artifact.o")],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    destructor = module.destructors[0]
    harness = tmp_path / "destructor-harness.c"
    if main_source == "return 0;":
        harness_body = (
            f'int main(void) {{ {_type(destructor.target)} value = {{ .field_0 = 23 }}; '
            f'{_destructor_c_name(destructor.target)}(&value); return 0; }}\n'
        )
    else:
        harness_body = "int main(void) { return merit_main(); }\n"
    harness.write_text('#include "destructor-artifact.c"\n' + harness_body,
                       encoding="utf-8", newline="\n")
    linked = subprocess.run(
        [compiler, "-std=c11", str(harness), "-o", str(tmp_path / "destructor-run.exe")],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    executed = subprocess.run([str(tmp_path / "destructor-run.exe")], capture_output=True, text=True)
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout == expected_output


@pytest.mark.parametrize("entry", ["emit_replacement_bundle", "emit_native_project_artifacts"])
def test_native_early_return_with_live_destructor_matches_oracle(tmp_path: Path, entry: str) -> None:
    repository = Path(__file__).resolve().parents[2]
    compiler_root = tmp_path / "compiler"
    shutil.copytree(repository / "examples/projects/bootstrap_lexer", compiler_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    manifest = compiler_root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '\n[executable]\nadapter = "stdin-string-i32"\n'
        + f'entry = "{entry}"\n',
        encoding="utf-8", newline="\n",
    )
    _, _, executable = build(load_project(manifest), tmp_path / "build" / "compiler")
    source_root = tmp_path / "input"
    (source_root / "src").mkdir(parents=True)
    (source_root / "Merit.toml").write_text(
        '[package]\nname = "probe"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n', encoding="utf-8", newline="\n",
    )
    (source_root / "src/main.mrt").write_text(
        "module probe\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "pub fn main()->i32 { let marker:Marker=Marker{number:23}; "
        "if (1 == 1) { return 0; } return 1; }\n",
        encoding="utf-8", newline="\n",
    )
    request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    if entry == "emit_replacement_bundle":
        bundle = decode_resolved_source_function_bundle(int(line) for line in completed.stdout.splitlines())
        assert len(bundle.functions) == 1
        assert len(bundle.functions[0].destructors) == 1
        return
    artifact = decode_native_project_artifact_transport(int(line) for line in completed.stdout.splitlines())
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert len(module.destructors) == 1
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    compiler = shutil.which("cc") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("C compiler unavailable")
    c_path = tmp_path / "early-return.c"
    c_path.write_bytes(artifact.c_source_bytes)
    harness = tmp_path / "harness.c"
    harness.write_text('#include "early-return.c"\nint main(void) { return merit_main(); }\n',
                       encoding="utf-8", newline="\n")
    linked = subprocess.run([compiler, "-std=c11", str(harness), "-o", str(tmp_path / "early-return.exe")],
                            capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    executed = subprocess.run([str(tmp_path / "early-return.exe")], capture_output=True, text=True)
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout == "23\n"


@pytest.mark.parametrize(("declarations", "expected_status"), [
    ("destructor Marker { print(self.number); }\n" * 2, 971),
    ("destructor Ghost { print(self.number); }\n", 992),
])
def test_native_source_destructor_catalog_fails_closed(
    tmp_path: Path, declarations: str, expected_status: int,
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
    source = (
        "module probe\nstruct Marker { number:i64; }\n"
        + declarations + "pub fn main()->i32 { return 0; }\n"
    ).encode("utf-8")
    request = encode_project_request(ProjectRequest(
        package="probe", entry="src/main.mrt",
        units=(ProjectRequestUnit(path="src/main.mrt", source=source),),
    ))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == expected_status, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stderr.strip() == f"replacement driver status {expected_status}".encode("ascii")
