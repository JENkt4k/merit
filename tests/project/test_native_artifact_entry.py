"""Black-box evidence for the Merit-owned v4 project artifact entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from merit.bootstrap.mir_contract import (
    MirBlock, MirFunction, MirInstruction, MirLocal, MirModule, MirTerminator, MirType,
)
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.resolved_source_function_bundle import (
    BUNDLE_MAGIC, PROJECT_ARTIFACT_BUNDLE_VERSION,
    decode_resolved_source_function_bundle,
    decode_native_project_artifact_transport,
)
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import encode_loaded_project_request


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_compiler_entry_emits_v4_artifacts_without_snapshot_decoder(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    compiler_root = tmp_path / "native-compiler"
    shutil.copytree(repository / "examples" / "projects" / "bootstrap_lexer", compiler_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    compiler_manifest = compiler_root / "Merit.toml"
    compiler_manifest.write_text(
        compiler_manifest.read_text(encoding="utf-8")
        + '\n[executable]\nadapter = "stdin-string-i32"\n'
        + 'entry = "emit_native_project_artifacts"\n',
        encoding="utf-8", newline="\n",
    )
    compiler = load_project(compiler_manifest)
    _, _, executable = build(compiler, tmp_path / "build" / "native-artifact-compiler")

    source_root = tmp_path / "input-project"
    (source_root / "src").mkdir(parents=True)
    (source_root / "Merit.toml").write_text(
        '[package]\nname = "probe"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n', encoding="utf-8", newline="\n",
    )
    (source_root / "src" / "main.mrt").write_text(
        "module probe\npub fn main()->i32 { return 1; }\n",
        encoding="utf-8", newline="\n",
    )
    request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    transport = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    assert transport.module_name == "probe"
    canonical = json.loads(transport.canonical_mir_bytes)
    assert canonical["schema"] == "bootstrap-mir-v1"
    assert canonical["name"] == "probe"
    assert [function["name"] for function in canonical["functions"]] == ["main"]
    assert b"merit_main" in transport.c_source_bytes
    assert b"merit_main" in transport.c_header_bytes

    (source_root / "src" / "main.mrt").write_text(
        "module probe\nfn helper()->i32 { return 7; }\n"
        "pub fn main()->i32 { return helper(); }\n",
        encoding="utf-8", newline="\n",
    )
    request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    transport = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    canonical = json.loads(transport.canonical_mir_bytes)
    assert [function["name"] for function in canonical["functions"]] == ["helper", "main"]
    assert b"helper(void)" in transport.c_source_bytes
    assert b"merit_main" in transport.c_header_bytes
    generated_c = tmp_path / "native-artifact.c"
    generated_c.write_bytes(transport.c_source_bytes)
    driver_c = tmp_path / "native-artifact-driver.c"
    driver_c.write_text(
        '#include "native-artifact.c"\n'
        'int main(void) { return merit_main() == 7 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    cc = shutil.which("cc") or shutil.which("gcc")
    assert cc is not None
    program = tmp_path / "native-artifact-program"
    subprocess.run([cc, "-std=c11", str(driver_c), "-o", str(program)],
                   check=True, capture_output=True)
    subprocess.run([str(program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\npub fn main()->i32 { print("hi"); return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    text_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    text_result = subprocess.run([str(executable)], input=text_request, capture_output=True)
    assert text_result.returncode == 0, text_result.stderr.decode("utf-8", errors="replace")
    text_transport = decode_native_project_artifact_transport(
        int(line) for line in text_result.stdout.splitlines()
    )
    assert b"merit_String" in text_transport.c_source_bytes
    text_c = tmp_path / "native-text.c"
    text_c.write_bytes(text_transport.c_source_bytes)
    text_driver = tmp_path / "native-text-driver.c"
    text_driver.write_text(
        '#include "native-text.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    text_program = tmp_path / "native-text-program"
    subprocess.run([cc, "-std=c11", str(text_driver), "-o", str(text_program)],
                   check=True, capture_output=True)
    text_stdout = subprocess.run([str(text_program)], check=True, capture_output=True).stdout
    assert text_stdout.replace(b"\r\n", b"\n") == b"hi\n"

    (source_root / "src" / "main.mrt").write_text(
        "module probe\npub fn main()->i32 { let byte:u8=33; print(byte); return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    byte_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    byte_result = subprocess.run([str(executable)], input=byte_request, capture_output=True)
    assert byte_result.returncode == 0, byte_result.stderr.decode("utf-8", errors="replace")
    byte_transport = decode_native_project_artifact_transport(
        int(line) for line in byte_result.stdout.splitlines()
    )
    assert b"UINT8_C(33)" in byte_transport.c_source_bytes
    byte_module = MirModule("probe", (MirFunction(
        "main", MirType("i32"), (
            MirLocal(0, "byte", MirType("u8"), source_binding_id=0),
            MirLocal(1, "_t0", MirType("u8")),
            MirLocal(2, "_t4", MirType("i32")),
        ), (MirBlock(0, (
            MirInstruction(0, "const", result=1, value=33, ownership="value"),
            MirInstruction(1, "copy", result=0, operands=(1,)),
            MirInstruction(2, "print", operands=(0,)),
            MirInstruction(3, "const", result=2, value=0, ownership="value"),
        ), MirTerminator("return", operands=(2,))),), 0, exported=True,
    ),))
    assert byte_transport.c_source_bytes.decode("utf-8") == emit_c_module(byte_module)
    assert byte_transport.c_header_bytes.decode("utf-8") == emit_c_header(byte_module)
    byte_c = tmp_path / "native-byte.c"
    byte_c.write_bytes(byte_transport.c_source_bytes)
    byte_driver = tmp_path / "native-byte-driver.c"
    byte_driver.write_text(
        '#include "native-byte.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    byte_program = tmp_path / "native-byte-program"
    subprocess.run([cc, "-std=c11", str(byte_driver), "-o", str(byte_program)],
                   check=True, capture_output=True)
    byte_stdout = subprocess.run([str(byte_program)], check=True, capture_output=True).stdout
    assert byte_stdout.replace(b"\r\n", b"\n") == b"33\n"

    (source_root / "src" / "main.mrt").write_text(
        "module probe\npub fn main()->i32 { let byte:u8=255; print(byte); return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    boundary_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    boundary_result = subprocess.run([str(executable)], input=boundary_request, capture_output=True)
    assert boundary_result.returncode == 0
    boundary = decode_native_project_artifact_transport(
        int(line) for line in boundary_result.stdout.splitlines()
    )
    assert b"UINT8_C(255)" in boundary.c_source_bytes

    (source_root / "src" / "main.mrt").write_text(
        "module probe\npub fn main()->i32 { let byte:u8=256; print(byte); return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    invalid_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    invalid_result = subprocess.run([str(executable)], input=invalid_request, capture_output=True)
    assert invalid_result.returncode != 0
    assert [int(line) for line in invalid_result.stdout.splitlines()[:3]] == [
        BUNDLE_MAGIC, PROJECT_ARTIFACT_BUNDLE_VERSION, 0,
    ]

    compiler_manifest.write_text(
        compiler_manifest.read_text(encoding="utf-8").replace(
            'entry = "emit_native_project_artifacts"',
            'entry = "emit_replacement_bundle"',
        ),
        encoding="utf-8", newline="\n",
    )
    legacy_compiler = load_project(compiler_manifest)
    _, _, legacy_executable = build(
        legacy_compiler, tmp_path / "build" / "legacy-bundle-compiler"
    )
    legacy = subprocess.run([str(legacy_executable)], input=request, capture_output=True)
    assert legacy.returncode == 0, legacy.stderr.decode("utf-8", errors="replace")
    bundle = decode_resolved_source_function_bundle(
        int(line) for line in legacy.stdout.splitlines()
    )
    assert bundle.module_name == "probe"
    assert len(bundle.functions) == 2
