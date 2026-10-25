"""SH3 acceptance artifacts match the independent MIR/C oracle and runtime."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.replacement_build import ReplacementBuildArtifact, compile_replacement_shared_artifact
from merit.bootstrap.replacement_project import ReplacementFunctionInput, build_replacement_project_artifact
from merit.bootstrap.resolved_source_function_bundle import (
    decode_native_project_artifact_transport,
    decode_resolved_source_function_bundle,
)
from merit.project.build import build
from merit.project.executable_adapter import link_executable_adapter
from merit.project.loader import load_project
from merit.project.project_request import (
    ProjectRequest, ProjectRequestUnit, encode_loaded_project_request, encode_project_request,
)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def compiler_paths(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    temporary = tmp_path_factory.mktemp("sh3-acceptance-compilers")
    compiler_root = temporary / "compiler"
    shutil.copytree(ROOT / "examples/projects/bootstrap_lexer", compiler_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    manifest = compiler_root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '\n[executable]\nadapter = "stdin-string-i32"\n'
        + 'entry = "emit_native_project_artifacts"\n',
        encoding="utf-8", newline="\n",
    )
    _, _, native = build(load_project(manifest), temporary / "native-compiler")
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'entry = "emit_native_project_artifacts"', 'entry = "emit_replacement_bundle"'
        ), encoding="utf-8", newline="\n",
    )
    _, _, legacy = build(load_project(manifest), temporary / "legacy-compiler")
    return native, legacy


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
@pytest.mark.parametrize("project_name, side_effect", [
    ("binary_packet", None),
    ("borrowed_views", None),
    ("cobol_finance_modernization", None),
    ("filesystem_capabilities", "merit-filesystem-capabilities.bin"),
    ("generic_collections", None),
    ("generic_result", None),
    ("ledger_app", "ledger_report.txt"),
    ("text_pipeline", None),
    ("trait_bounds", None),
])
def test_native_acceptance_project_matches_oracle(
    compiler_paths: tuple[Path, Path], tmp_path: Path, project_name: str,
    side_effect: str | None,
) -> None:
    project = load_project(ROOT / "examples/projects" / project_name / "Merit.toml")
    request = encode_loaded_project_request(project, header_exports=())
    native_compiler, legacy_compiler = compiler_paths
    native_response = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert native_response.returncode == 0, native_response.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in native_response.stdout.splitlines()
    )
    legacy_response = subprocess.run([str(legacy_compiler)], input=request, capture_output=True)
    assert legacy_response.returncode == 0, legacy_response.stderr.decode("utf-8", errors="replace")
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in legacy_response.stdout.splitlines()
    )
    oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=bytes(bundle.functions[0].effective_source_bytes).decode("utf-8"),
                module_name=bundle.module_name,
                snapshot_values=values,
                capability_names={index: name for index, name in enumerate(bundle.capability_names)},
            )
            for values in bundle.encoded_snapshots
        ), module_name=bundle.module_name,
    )
    assert artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        module, exported_names=frozenset()
    )

    generated = tmp_path / "native.c"
    generated.write_bytes(artifact.c_source_bytes)
    c_compiler = shutil.which("cc") or shutil.which("gcc")
    assert c_compiler is not None
    executable = tmp_path / "native.exe"
    linked = subprocess.run(
        [c_compiler, "-std=c11", str(generated), "-o", str(executable)],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    _, _, reference = build(project, tmp_path / "reference" / "program")
    native_directory = tmp_path / "native-run"
    reference_directory = tmp_path / "reference-run"
    native_directory.mkdir()
    reference_directory.mkdir()
    native_run = subprocess.run([str(executable)], cwd=native_directory, capture_output=True)
    reference_run = subprocess.run([str(reference)], cwd=reference_directory, capture_output=True)
    assert native_run.returncode == reference_run.returncode == 0
    assert native_run.stdout == reference_run.stdout
    if side_effect is not None:
        assert (native_directory / side_effect).read_bytes() == (
            reference_directory / side_effect
        ).read_bytes()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_payload_free_enum_storage_matches_alpha2_oracle(
    compiler_paths: tuple[Path, Path], tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    (source_root / "src").mkdir(parents=True)
    (source_root / "Merit.toml").write_text(
        '[package]\nname = "probe"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n', encoding="utf-8", newline="\n",
    )
    (source_root / "src/main.mrt").write_text(
        "module probe\nstruct Marker { number:i32; }\n"
        "destructor Marker { print(self.number); }\n"
        "enum Maybe { SomeMarker(Marker), NoMarker }\n"
        "pub fn main()->i32 { let marker:Marker=Marker{number:23}; "
        "let value:Maybe=SomeMarker(marker); return 7; }\n",
        encoding="utf-8", newline="\n",
    )
    project = load_project(source_root / "Merit.toml")
    request = encode_loaded_project_request(project, header_exports=())
    native_compiler, legacy_compiler = compiler_paths
    native_response = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert native_response.returncode == 0, native_response.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in native_response.stdout.splitlines()
    )
    legacy_response = subprocess.run([str(legacy_compiler)], input=request, capture_output=True)
    assert legacy_response.returncode == 0, legacy_response.stderr.decode("utf-8", errors="replace")
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in legacy_response.stdout.splitlines()
    )
    oracle = build_replacement_project_artifact((
        ReplacementFunctionInput.from_values(
            source=bytes(bundle.functions[0].effective_source_bytes).decode("utf-8"),
            module_name=bundle.module_name, snapshot_values=values,
            capability_names={index: name for index, name in enumerate(bundle.capability_names)},
        ) for values in bundle.encoded_snapshots
    ), module_name=bundle.module_name)
    assert artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert any(
        len(local.type.arguments) == 2 and local.type.arguments[1].name == "i64"
        for function in module.functions for local in function.locals
        if local.type.name.startswith("enum_owned_payload_")
    )
    c_source = artifact.c_source_bytes.decode("utf-8")
    assert c_source == oracle.c_source
    assert "int64_t variant_1;" in c_source
    generated = tmp_path / "native.c"
    generated.write_bytes(artifact.c_source_bytes)
    harness = tmp_path / "harness.c"
    harness.write_text('#include "native.c"\nint main(void) { return merit_main(); }\n',
                       encoding="utf-8", newline="\n")
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    executable = tmp_path / "native.exe"
    subprocess.run([compiler, "-std=c11", str(harness), "-o", str(executable)],
                   check=True, capture_output=True, text=True)
    _, _, reference = build(project, tmp_path / "reference" / "program")
    native_run = subprocess.run([str(executable)], capture_output=True)
    reference_run = subprocess.run([str(reference)], capture_output=True)
    assert native_run.returncode == reference_run.returncode == 7
    assert native_run.stdout == reference_run.stdout
    assert native_run.stdout.replace(b"\r\n", b"\n") == b"23\n"


def test_native_compiler_project_emits_deterministic_complete_artifact(
    compiler_paths: tuple[Path, Path],
) -> None:
    project = load_project(ROOT / "examples" / "projects" / "bootstrap_lexer" / "Merit.toml")
    request = encode_loaded_project_request(project, header_exports=())
    native_compiler, _ = compiler_paths
    first = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert first.returncode == 0, first.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in first.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert module.functions
    assert artifact.c_source_bytes
    assert artifact.c_header_bytes

    second = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert second.returncode == 0, second.stderr.decode("utf-8", errors="replace")
    assert second.stdout == first.stdout


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_compiler_project_c_matches_oracle_and_compiles(
    compiler_paths: tuple[Path, Path], tmp_path: Path,
) -> None:
    project = load_project(ROOT / "examples" / "projects" / "bootstrap_lexer" / "Merit.toml")
    request = encode_loaded_project_request(project, header_exports=())
    native_compiler, _ = compiler_paths
    response = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert response.returncode == 0, response.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in response.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        module, exported_names=frozenset()
    )
    generated = tmp_path / "compiler.c"
    generated.write_bytes(artifact.c_source_bytes)
    c_compiler = shutil.which("cc") or shutil.which("gcc")
    assert c_compiler is not None
    compiled = subprocess.run(
        [c_compiler, "-std=c11", "-fsyntax-only", str(generated)],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr

    executable = tmp_path / "native-compiler-main.exe"
    linked = subprocess.run(
        [c_compiler, "-std=c11", str(generated), "-o", str(executable)],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    _, _, reference = build(project, tmp_path / "reference-compiler-main")
    native_run = subprocess.run([str(executable)], capture_output=True, timeout=30)
    reference_run = subprocess.run([str(reference)], capture_output=True, timeout=30)
    assert (native_run.returncode, native_run.stdout, native_run.stderr) == (
        reference_run.returncode, reference_run.stdout, reference_run.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_compiler_artifact_adapter_matches_stage_zero_protocol(
    compiler_paths: tuple[Path, Path], tmp_path: Path,
) -> None:
    project = load_project(ROOT / "examples" / "projects" / "bootstrap_lexer" / "Merit.toml")
    request = encode_loaded_project_request(
        project, header_exports=frozenset({"emit_native_project_artifacts"}),
    )
    stage_zero, _ = compiler_paths
    response = subprocess.run([str(stage_zero)], input=request, capture_output=True)
    assert response.returncode == 0, response.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in response.stdout.splitlines()
    )
    _, _, library = compile_replacement_shared_artifact(
        ReplacementBuildArtifact(
            module=None,
            c_source=artifact.c_source_bytes.decode("utf-8"),
            c_header=artifact.c_header_bytes.decode("utf-8"),
        ),
        tmp_path / "native-compiler-library",
        header_exports=frozenset({"emit_native_project_artifacts"}),
    )
    stage_one = link_executable_adapter(
        tmp_path / "native-compiler-stage-one",
        library=library,
        adapter="stdin-string-i32",
        entry="emit_native_project_artifacts",
    )
    accepted_probe = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt",
        (ProjectRequestUnit("src/main.mrt", b"module probe\nfn main()->i32 { return 7; }\n"),),
        header_exports=(),
    ))
    rejected_probe = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt",
        (ProjectRequestUnit("src/main.mrt", b"module probe\nfn main()->i32 { return ; }\n"),),
        header_exports=(),
    ))
    capability_probe = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt",
        (ProjectRequestUnit(
            "src/main.mrt",
            b"module probe\ncapability allocate;\n"
            b"fn main()->i32 { let allocator:Allocator=system_allocator(); "
            b"let data:Buffer=buffer_new(allocator,8); drop(data); return 0; }\n",
        ),),
        header_exports=(),
    ))
    unsupported_version_probe = b"MPRQ" + (99).to_bytes(4, "big")
    for probe in (accepted_probe, rejected_probe, capability_probe, unsupported_version_probe):
        expected = subprocess.run([str(stage_zero)], input=probe, capture_output=True, timeout=30)
        actual = subprocess.run([str(stage_one)], input=probe, capture_output=True, timeout=30)
        if probe is not accepted_probe:
            assert expected.returncode != 0, expected.stdout
        if probe is unsupported_version_probe:
            assert expected.returncode == 4606, expected.stderr
        assert (actual.returncode, actual.stdout, actual.stderr) == (
            expected.returncode, expected.stdout, expected.stderr,
        )


def test_native_compiler_project_mir_matches_independent_oracle(
    compiler_paths: tuple[Path, Path],
) -> None:
    project = load_project(ROOT / "examples" / "projects" / "bootstrap_lexer" / "Merit.toml")
    request = encode_loaded_project_request(project, header_exports=())
    native_compiler, legacy_compiler = compiler_paths
    native_response = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert native_response.returncode == 0, native_response.stderr.decode(
        "utf-8", errors="replace"
    )
    artifact = decode_native_project_artifact_transport(
        int(line) for line in native_response.stdout.splitlines()
    )
    legacy_response = subprocess.run([str(legacy_compiler)], input=request, capture_output=True)
    assert legacy_response.returncode == 0, legacy_response.stderr.decode(
        "utf-8", errors="replace"
    )
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in legacy_response.stdout.splitlines()
    )
    oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=bytes(bundle.functions[0].effective_source_bytes).decode("utf-8"),
                module_name=bundle.module_name,
                snapshot_values=values,
                capability_names={index: name for index, name in enumerate(bundle.capability_names)},
            )
            for values in bundle.encoded_snapshots
        ), module_name=bundle.module_name,
    )
    expected = canonical_mir_json(oracle.module).encode("utf-8")
    actual = artifact.canonical_mir_bytes
    if actual != expected:
        first_difference = next(
            (index for index, (left, right) in enumerate(zip(actual, expected)) if left != right),
            min(len(actual), len(expected)),
        )
        pytest.fail(
            "full compiler canonical MIR differs from independent oracle: "
            f"byte={first_difference}, native={len(actual)} bytes/"
            f"{hashlib.sha256(actual).hexdigest()}, oracle={len(expected)} bytes/"
            f"{hashlib.sha256(expected).hexdigest()}"
        )


@pytest.mark.parametrize("body", [
    'let result:i64 = file_read(allocator, "missing.bin");',
    'let result:FileWriteResult = file_write("out.bin", 7);',
])
def test_native_filesystem_call_rejects_invalid_source(
    compiler_paths: tuple[Path, Path], body: str,
) -> None:
    source = (
        "module invalid_filesystem\n"
        "capability allocate;\ncapability file_read;\ncapability file_write;\n"
        "fn main()->i32 { with capability allocate {\n"
        "let allocator:Allocator = system_allocator();\n"
        "with capability file_read { with capability file_write {\n"
        f"{body}\n"
        "} } } return 0; }\n"
    ).encode("utf-8")
    request = encode_project_request(ProjectRequest(
        "invalid_filesystem", "src/main.mrt",
        (ProjectRequestUnit("src/main.mrt", source),), header_exports=(),
    ))
    native_compiler, _ = compiler_paths
    response = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert response.returncode != 0
    assert b"replacement driver status" in response.stderr


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
@pytest.mark.parametrize(("module_name", "source", "expected_output"), [
    (
        "vector_borrow",
        "module vector_borrow\ncapability allocate;\n"
        "fn append(borrow_mut values:Vec<i64>)->i64 requires_caps [allocate] {\n"
        "    vec_push<i64>(values, 7); return vec_len<i64>(values);\n}\n"
        "fn main()->i32 { with capability allocate {\n"
        "    let allocator:Allocator=system_allocator();\n"
        "    var values:Vec<i64>=vec_new<i64>(allocator, 0);\n"
        "    print(append(values)); drop(values);\n"
        "} return 0; }\n",
        [b"1"],
    ),
    (
        "vector_return_after_loop",
        "module vector_return_after_loop\ncapability allocate;\n"
        "fn make()->Vec<i64> requires_caps [allocate] {\n"
        "    let allocator:Allocator=system_allocator();\n"
        "    var values:Vec<i64>=vec_new<i64>(allocator, 0);\n"
        "    var index:i64=0;\n"
        "    while index<2 { vec_push<i64>(values,index); index=checked_add(index,1); }\n"
        "    return values;\n}\n"
        "fn main()->i32 { with capability allocate {\n"
        "    var values:Vec<i64>=make(); print(vec_len<i64>(values)); drop(values);\n"
        "} return 0; }\n",
        [b"2"],
    ),
    (
        "vector_mutable_reborrow",
        "module vector_mutable_reborrow\ncapability allocate;\n"
        "fn count(borrow values:Vec<i64>)->i64 { return vec_len<i64>(values); }\n"
        "fn append_and_count(borrow_mut values:Vec<i64>)->i64 requires_caps [allocate] {\n"
        "    vec_push<i64>(values,7); return count(values);\n}\n"
        "fn main()->i32 { with capability allocate {\n"
        "    let allocator:Allocator=system_allocator();\n"
        "    var values:Vec<i64>=vec_new<i64>(allocator,0);\n"
        "    print(append_and_count(values)); drop(values);\n"
        "} return 0; }\n",
        [b"1"],
    ),
    (
        "bool_into_i32",
        "module bool_into_i32\n"
        "fn main()->i32 { let flag:i32=1==1; print(flag); return 0; }\n",
        [b"1"],
    ),
], ids=["borrowed-vector-parameter", "owned-vector-return-after-loop", "mutable-to-shared-reborrow", "bool-into-i32"])
def test_native_resource_and_coercion_flow_matches_oracle(
    compiler_paths: tuple[Path, Path], tmp_path: Path,
    module_name: str, source: str, expected_output: list[bytes],
) -> None:
    request = encode_project_request(ProjectRequest(
        module_name, "src/main.mrt",
        (ProjectRequestUnit("src/main.mrt", source.encode("utf-8")),), header_exports=(),
    ))
    native_compiler, legacy_compiler = compiler_paths
    native_response = subprocess.run([str(native_compiler)], input=request, capture_output=True)
    assert native_response.returncode == 0, native_response.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in native_response.stdout.splitlines()
    )
    legacy_response = subprocess.run([str(legacy_compiler)], input=request, capture_output=True)
    assert legacy_response.returncode == 0
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in legacy_response.stdout.splitlines()
    )
    oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=bytes(bundle.functions[0].effective_source_bytes).decode("utf-8"),
                module_name=bundle.module_name,
                snapshot_values=values,
                capability_names={index: name for index, name in enumerate(bundle.capability_names)},
            )
            for values in bundle.encoded_snapshots
        ), module_name=bundle.module_name,
    )
    assert artifact.canonical_mir_bytes == canonical_mir_json(oracle.module).encode("utf-8")
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(
        module, exported_names=frozenset()
    )
    generated = tmp_path / "vector-resource.c"
    generated.write_bytes(artifact.c_source_bytes)
    c_compiler = shutil.which("cc") or shutil.which("gcc")
    assert c_compiler is not None
    executable = tmp_path / "vector-resource.exe"
    linked = subprocess.run([c_compiler, "-std=c11", str(generated), "-o", str(executable)],
                            capture_output=True, text=True)
    assert linked.returncode == 0, linked.stderr
    native_run = subprocess.run([str(executable)], capture_output=True)
    assert native_run.returncode == 0
    assert native_run.stdout.splitlines() == expected_output
