"""SH3 regression: native project artifacts retain explicit destructors."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CompileError
from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.mir_to_c import _destructor_c_name, _type, emit_c_header, emit_c_module
from merit.bootstrap.replacement_project import (
    ReplacementFunctionInput,
    build_replacement_project_artifact,
)
from merit.bootstrap.resolved_source_function_snapshot import decode_resolved_source_function_snapshot
from merit.bootstrap.resolved_source_function_bundle import (
    ResolvedSourceFunctionBundleError,
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


def test_native_cross_module_conflicting_destructor_rejects(tmp_path: Path) -> None:
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
    helper_source = (
        "module helper\npub struct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "pub fn get()->i32 { return 1; }\n"
    )
    main_source = (
        "module probe\nimport helper;\n"
        "destructor Marker { print(self.number); }\n"
        "pub fn main()->i32 { return helper.get(); }\n"
    )
    source_root = tmp_path / "input"
    (source_root / "src").mkdir(parents=True)
    (source_root / "Merit.toml").write_text(
        '[package]\nname = "probe"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n', encoding="utf-8", newline="\n",
    )
    (source_root / "src/helper.mrt").write_text(helper_source, encoding="utf-8", newline="\n")
    (source_root / "src/main.mrt").write_text(main_source, encoding="utf-8", newline="\n")
    with pytest.raises(CompileError, match="M5500: duplicate destructor"):
        load_project(source_root / "Merit.toml")
    request = encode_project_request(ProjectRequest(
        package="probe", entry="src/main.mrt",
        units=(
            ProjectRequestUnit(path="src/helper.mrt", source=helper_source.encode("utf-8")),
            ProjectRequestUnit(path="src/main.mrt", source=main_source.encode("utf-8")),
        ),
    ))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 971, completed.stderr.decode("utf-8", errors="replace")
    with pytest.raises(ResolvedSourceFunctionBundleError, match="missing metadata"):
        decode_native_project_artifact_transport(int(line) for line in completed.stdout.splitlines())
    assert completed.stderr.strip() == b"replacement driver status 971"


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
@pytest.mark.parametrize("local_destructor", (False, True), ids=("imported-only", "two-modules"))
def test_native_multimodule_destructor_artifact_matches_oracle(
    tmp_path: Path, local_destructor: bool,
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
    local_declarations = (
        "struct Local { number:i64; }\n"
        "destructor Local { print(self.number); }\n"
        if local_destructor else ""
    )
    main_body = (
        "let marker:Marker=Marker{number:23}; "
        + ("let local:Local=Local{number:5}; " if local_destructor else "")
        + "return helper.get();"
    )
    request = encode_project_request(ProjectRequest(
        package="probe", entry="src/main.mrt",
        units=(
            ProjectRequestUnit(
                path="src/helper.mrt",
                source=(
                    "module helper\npub struct Marker { number:i64; }\n"
                    "destructor Marker { print(self.number); }\n"
                    "pub fn get()->i32 { return 1; }\n"
                ).encode("utf-8"),
            ),
            ProjectRequestUnit(
                path="src/main.mrt",
                source=(
                    "module probe\nimport helper;\n"
                    + local_declarations
                    + f"pub fn main()->i32 {{ {main_body} }}\n"
                ).encode("utf-8"),
            ),
        ),
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
    assert len(bundle.functions) == 2
    oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=bytes(bundle.functions[0].effective_source_bytes).decode("utf-8"),
                module_name=bundle.module_name,
                snapshot_values=values,
                capability_names={index + 1: name for index, name in enumerate(bundle.capability_names)},
            )
            for values in bundle.encoded_snapshots
        ),
        module_name=bundle.module_name,
    )
    assert artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert len(module.functions) == 2
    assert len(module.destructors) == 1 + int(local_destructor)
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    c_path = tmp_path / "multimodule.c"
    c_path.write_bytes(artifact.c_source_bytes)
    harness = tmp_path / "multimodule-harness.c"
    harness.write_text('#include "multimodule.c"\nint main(void) { return merit_main(); }\n',
                       encoding="utf-8", newline="\n")
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    linked = subprocess.run([compiler, "-std=c11", str(harness), "-o", str(tmp_path / "multimodule.exe")],
                            capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    executed = subprocess.run([str(tmp_path / "multimodule.exe")], capture_output=True, text=True)
    assert executed.returncode == 1, executed.stderr
    assert executed.stdout == ("5\n23\n" if local_destructor else "23\n")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
@pytest.mark.parametrize(("outer_fields", "outer_destructor", "main_source", "expected_output"), [
    ("inner:Inner;", "", "let outer:Outer=Outer{inner:Inner{number:23}}; return 0;", "23\n"),
    ("inner:Inner;", "", "let outer:Outer=Outer{inner:Inner{number:23}}; drop(outer); return 0;", "23\n"),
    ("inner:Inner; other:i64;", "",
     "let outer:Outer=Outer{inner:Inner{number:23},other:5}; return 0;", "23\n"),
    ("inner:Inner; other:i64;", "destructor Outer { print(self.other); }\n",
     "let outer:Outer=Outer{inner:Inner{number:23},other:5}; return 0;", "5\n23\n"),
    ("inner:Inner;", "",
     "let inner:Inner=Inner{number:23}; let outer:Outer=Outer{inner:inner}; return 0;", "23\n"),
    ("inner:Inner;", "",
     "var outer:Outer=Outer{inner:Inner{number:23}}; "
     "let replacement:Outer=Outer{inner:Inner{number:5}}; "
     "replace(outer,replacement); return 0;", "23\n5\n"),
    ("inner:Inner;", "",
     "var outer:Outer=Outer{inner:Inner{number:23}}; "
     "replace(outer,Outer{inner:Inner{number:5}}); return 0;", "23\n5\n"),
], ids=("owned-implicit", "owned-explicit", "aggregate-implicit", "aggregate-custom",
        "moved-child", "replaced-owned-child", "replaced-inline-owned-child"))
def test_native_nested_owned_field_destructor_cleanup_matches_oracle(
    tmp_path: Path, outer_fields: str, outer_destructor: str,
    main_source: str, expected_output: str,
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
        "module probe\n"
        "struct Inner { number:i64; }\n"
        "destructor Inner { print(self.number); }\n"
        f"struct Outer {{ {outer_fields} }}\n"
        + outer_destructor
        + f"pub fn main()->i32 {{ {main_source} }}\n"
    ).encode("utf-8")
    request = encode_project_request(ProjectRequest(
        package="probe", entry="src/main.mrt",
        units=(ProjectRequestUnit(path="src/main.mrt", source=source),),
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
        ),
        module_name=bundle.module_name,
    )
    assert artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert len(module.destructors) == 1 + bool(outer_destructor)
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    c_path = tmp_path / "nested-owned.c"
    c_path.write_bytes(artifact.c_source_bytes)
    harness = tmp_path / "nested-owned-harness.c"
    harness.write_text('#include "nested-owned.c"\nint main(void) { return merit_main(); }\n',
                       encoding="utf-8", newline="\n")
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    linked = subprocess.run([compiler, "-std=c11", str(harness), "-o", str(tmp_path / "nested-owned.exe")],
                            capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    executed = subprocess.run([str(tmp_path / "nested-owned.exe")], capture_output=True, text=True)
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout == expected_output
