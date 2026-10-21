"""SH3 acceptance artifacts match the independent MIR/C oracle and runtime."""

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
], ids=["borrowed-vector-parameter", "owned-vector-return-after-loop", "mutable-to-shared-reborrow"])
def test_native_vector_resource_flow_matches_oracle(
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
