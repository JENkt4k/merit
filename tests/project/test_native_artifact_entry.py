"""Black-box evidence for the Merit-owned v4 project artifact entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from merit.bootstrap.mir_contract import (
    MirBlock, MirFunction, MirInstruction, MirLocal, MirModule, MirTerminator, MirType,
    canonical_mir_json, parse_mir,
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
    canonical_mir = parse_mir(canonical)
    assert transport.c_source_bytes.decode("utf-8") == emit_c_module(canonical_mir)
    assert transport.c_header_bytes.decode("utf-8") == emit_c_header(canonical_mir)
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
    text_mir = parse_mir(json.loads(text_transport.canonical_mir_bytes))
    assert text_transport.c_source_bytes.decode("utf-8") == emit_c_module(text_mir)
    assert text_transport.c_header_bytes.decode("utf-8") == emit_c_header(text_mir)
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

    for index, (value, ensure_ascii) in enumerate((
        ("line\nnext", True), ('quote " and slash \\', True),
        ("é", True), ("😀", True), ("\u0001", True),
        ("é", False), ("😀", False),
    )):
        literal = json.dumps(value, ensure_ascii=ensure_ascii)
        (source_root / "src" / "main.mrt").write_text(
            f"module probe\npub fn main()->i32 {{ print({literal}); return 0; }}\n",
            encoding="utf-8", newline="\n",
        )
        escaped_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
        escaped_result = subprocess.run([str(executable)], input=escaped_request, capture_output=True)
        assert escaped_result.returncode == 0, escaped_result.stderr.decode("utf-8", errors="replace")
        escaped = decode_native_project_artifact_transport(
            int(line) for line in escaped_result.stdout.splitlines()
        )
        escaped_mir = parse_mir(json.loads(escaped.canonical_mir_bytes))
        assert escaped.canonical_mir_bytes.decode("utf-8") == canonical_mir_json(escaped_mir)
        assert escaped.c_source_bytes.decode("utf-8") == emit_c_module(escaped_mir)
        assert escaped.c_header_bytes.decode("utf-8") == emit_c_header(escaped_mir)
        escaped_c = tmp_path / f"native-escaped-{index}.c"
        escaped_c.write_bytes(escaped.c_source_bytes)
        escaped_driver = tmp_path / f"native-escaped-{index}-driver.c"
        escaped_driver.write_text(
            f'#include "native-escaped-{index}.c"\n'
            'int main(void) { return merit_main(); }\n',
            encoding="utf-8", newline="\n",
        )
        escaped_program = tmp_path / f"native-escaped-{index}-program"
        subprocess.run([cc, "-std=c11", str(escaped_driver), "-o", str(escaped_program)],
                       check=True, capture_output=True)
        escaped_stdout = subprocess.run([str(escaped_program)], check=True,
                                        capture_output=True).stdout
        assert escaped_stdout.replace(b"\r\n", b"\n") == value.encode("utf-8") + b"\n"

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nfn helper(borrow value:String)->i32 { return 1; }\n'
        'pub fn main()->i32 { let value:String="x"; return helper(value); }\n',
        encoding="utf-8", newline="\n",
    )
    borrowed_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    borrowed_result = subprocess.run([str(executable)], input=borrowed_request, capture_output=True)
    assert borrowed_result.returncode == 0, borrowed_result.stderr.decode("utf-8", errors="replace")
    borrowed = decode_native_project_artifact_transport(
        int(line) for line in borrowed_result.stdout.splitlines()
    )
    borrowed_c = tmp_path / "native-borrowed.c"
    borrowed_c.write_bytes(borrowed.c_source_bytes)
    borrowed_driver = tmp_path / "native-borrowed-driver.c"
    borrowed_driver.write_text(
        '#include "native-borrowed.c"\n'
        'int main(void) { return merit_main() == 1 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    borrowed_program = tmp_path / "native-borrowed-program"
    subprocess.run([cc, "-std=c11", str(borrowed_driver), "-o", str(borrowed_program)],
                   check=True, capture_output=True)
    subprocess.run([str(borrowed_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nfn helper(borrow value:String)->i32 { return 1; }\n'
        'pub fn main()->i32 { return helper("x"); }\n',
        encoding="utf-8", newline="\n",
    )
    temporary_borrow_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    temporary_borrow = subprocess.run([str(executable)], input=temporary_borrow_request,
                                      capture_output=True)
    assert temporary_borrow.returncode != 0
    assert [int(line) for line in temporary_borrow.stdout.splitlines()[:3]] == [
        BUNDLE_MAGIC, PROJECT_ARTIFACT_BUNDLE_VERSION, 0,
    ]

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nfn helper(borrow value:String)->i64 { return string_len(value); }\n'
        'pub fn main(borrow value:String)->i64 { return helper(value); }\n',
        encoding="utf-8", newline="\n",
    )
    forwarded_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    forwarded_result = subprocess.run([str(executable)], input=forwarded_request, capture_output=True)
    assert forwarded_result.returncode == 0, forwarded_result.stderr.decode("utf-8", errors="replace")
    forwarded = decode_native_project_artifact_transport(
        int(line) for line in forwarded_result.stdout.splitlines()
    )
    forwarded_mir = parse_mir(json.loads(forwarded.canonical_mir_bytes))
    assert forwarded.c_source_bytes.decode("utf-8") == emit_c_module(forwarded_mir)
    assert forwarded.c_header_bytes.decode("utf-8") == emit_c_header(forwarded_mir)
    forwarded_c = tmp_path / "native-forwarded.c"
    forwarded_c.write_bytes(forwarded.c_source_bytes)
    forwarded_driver = tmp_path / "native-forwarded-driver.c"
    forwarded_driver.write_text(
        '#include "native-forwarded.c"\n'
        'int main(void) { merit_String value = {(const uint8_t *)"xy", 2}; '
        'return merit_main(&value) == 2 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    forwarded_program = tmp_path / "native-forwarded-program"
    subprocess.run([cc, "-std=c11", str(forwarded_driver), "-o", str(forwarded_program)],
                   check=True, capture_output=True)
    subprocess.run([str(forwarded_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\n'
        'fn helper(view:ByteSlice)->i64 { return slice_len(view); }\n'
        'fn caller(view:ByteSlice)->i64 { return helper(view); }\n',
        encoding="utf-8", newline="\n",
    )
    slice_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    slice_result = subprocess.run([str(executable)], input=slice_request, capture_output=True)
    assert slice_result.returncode == 0, slice_result.stderr.decode("utf-8", errors="replace")
    slice_transport = decode_native_project_artifact_transport(
        int(line) for line in slice_result.stdout.splitlines()
    )
    slice_mir = parse_mir(json.loads(slice_transport.canonical_mir_bytes))
    assert slice_transport.c_source_bytes.decode("utf-8") == emit_c_module(slice_mir)
    assert slice_transport.c_header_bytes.decode("utf-8") == emit_c_header(slice_mir)
    slice_c = tmp_path / "native-slice-call.c"
    slice_c.write_bytes(slice_transport.c_source_bytes)
    slice_driver = tmp_path / "native-slice-call-driver.c"
    slice_driver.write_text(
        '#include "native-slice-call.c"\n'
        'int main(void) { const uint8_t data[] = {10, 20}; '
        'merit_ByteSlice view = {data, 2}; return caller(view) == 2 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    slice_program = tmp_path / "native-slice-call-program"
    subprocess.run([cc, "-std=c11", str(slice_driver), "-o", str(slice_program)],
                   check=True, capture_output=True)
    subprocess.run([str(slice_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nfn helper(borrow value:String,index:i64)->u8 {'
        ' return string_byte(value,index); }\n'
        'pub fn main(borrow value:String,index:i64)->u8 {'
        ' return helper(value,index); }\n',
        encoding="utf-8", newline="\n",
    )
    byte_borrow_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    byte_borrow_result = subprocess.run([str(executable)], input=byte_borrow_request, capture_output=True)
    assert byte_borrow_result.returncode == 0, byte_borrow_result.stderr.decode("utf-8", errors="replace")
    byte_borrow = decode_native_project_artifact_transport(
        int(line) for line in byte_borrow_result.stdout.splitlines()
    )
    byte_borrow_mir = parse_mir(json.loads(byte_borrow.canonical_mir_bytes))
    assert byte_borrow.c_source_bytes.decode("utf-8") == emit_c_module(byte_borrow_mir)
    assert byte_borrow.c_header_bytes.decode("utf-8") == emit_c_header(byte_borrow_mir)
    byte_borrow_c = tmp_path / "native-borrowed-byte.c"
    byte_borrow_c.write_bytes(byte_borrow.c_source_bytes)
    byte_borrow_driver = tmp_path / "native-borrowed-byte-driver.c"
    byte_borrow_driver.write_text(
        '#include "native-borrowed-byte.c"\n'
        'int main(void) { merit_String value = {(const uint8_t *)"xy", 2}; '
        'return merit_main(&value, 1) == 121 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    byte_borrow_program = tmp_path / "native-borrowed-byte-program"
    subprocess.run([cc, "-std=c11", str(byte_borrow_driver), "-o", str(byte_borrow_program)],
                   check=True, capture_output=True)
    subprocess.run([str(byte_borrow_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nfn helper(borrow value:Buffer)->i64 { return buffer_len(value); }\n'
        'fn entry(borrow value:Buffer)->i64 { return helper(value); }\n',
        encoding="utf-8", newline="\n",
    )
    buffer_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    buffer_result = subprocess.run([str(executable)], input=buffer_request, capture_output=True)
    assert buffer_result.returncode == 0, buffer_result.stderr.decode("utf-8", errors="replace")
    buffer_transport = decode_native_project_artifact_transport(
        int(line) for line in buffer_result.stdout.splitlines()
    )
    buffer_mir = parse_mir(json.loads(buffer_transport.canonical_mir_bytes))
    assert all(function.locals[0].ownership == "borrowed" for function in buffer_mir.functions)
    assert all(instruction.kind != "drop" for function in buffer_mir.functions
               for block in function.blocks for instruction in block.instructions)
    assert buffer_transport.c_source_bytes.decode("utf-8") == emit_c_module(buffer_mir)
    assert buffer_transport.c_header_bytes.decode("utf-8") == emit_c_header(buffer_mir)
    buffer_c = tmp_path / "native-borrowed-buffer.c"
    buffer_c.write_bytes(buffer_transport.c_source_bytes)
    buffer_driver = tmp_path / "native-borrowed-buffer-driver.c"
    buffer_driver.write_text(
        '#include "native-borrowed-buffer.c"\n'
        'int main(void) { merit_Buffer value = {0}; return entry(&value) == 0 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    buffer_program = tmp_path / "native-borrowed-buffer-program"
    subprocess.run([cc, "-std=c11", str(buffer_driver), "-o", str(buffer_program)],
                   check=True, capture_output=True)
    subprocess.run([str(buffer_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\ncapability allocate;\n'
        'pub fn main()->i32 { with capability allocate {'
        ' let allocator:Allocator=system_allocator();'
        ' var data:Buffer=buffer_from_string(allocator,"x");'
        ' drop(data); } return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    drop_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    drop_result = subprocess.run([str(executable)], input=drop_request, capture_output=True)
    assert drop_result.returncode == 0, drop_result.stderr.decode("utf-8", errors="replace")
    drop_transport = decode_native_project_artifact_transport(
        int(line) for line in drop_result.stdout.splitlines()
    )
    drop_mir = json.loads(drop_transport.canonical_mir_bytes)
    drop_kinds = [instruction["kind"] for function in drop_mir["functions"]
                  for block in function["blocks"] for instruction in block["instructions"]]
    assert "drop" in drop_kinds
    assert drop_kinds[-1] == "const"
    drop_c = tmp_path / "native-drop-before-const.c"
    drop_c.write_bytes(drop_transport.c_source_bytes)
    drop_driver = tmp_path / "native-drop-before-const-driver.c"
    drop_driver.write_text(
        '#include "native-drop-before-const.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    drop_program = tmp_path / "native-drop-before-const-program"
    subprocess.run([cc, "-std=c11", str(drop_driver), "-o", str(drop_program)],
                   check=True, capture_output=True)
    subprocess.run([str(drop_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\npub fn main(start:i64,limit:i64,step:i64)->i64 {'
        ' var count:i64=start; while (count<limit) {'
        ' count=checked_add(count,step); } return count; }\n',
        encoding="utf-8", newline="\n",
    )
    loop_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    loop_result = subprocess.run([str(executable)], input=loop_request, capture_output=True)
    assert loop_result.returncode == 0, loop_result.stderr.decode("utf-8", errors="replace")
    loop_transport = decode_native_project_artifact_transport(
        int(line) for line in loop_result.stdout.splitlines()
    )
    loop_mir = json.loads(loop_transport.canonical_mir_bytes)
    assert len(loop_mir["functions"][0]["blocks"]) > 1
    assert loop_transport.c_source_bytes.decode("utf-8") == emit_c_module(parse_mir(loop_mir))
    assert loop_transport.c_header_bytes.decode("utf-8") == emit_c_header(parse_mir(loop_mir))
    loop_c = tmp_path / "native-loop.c"
    loop_c.write_bytes(loop_transport.c_source_bytes)
    loop_driver = tmp_path / "native-loop-driver.c"
    loop_driver.write_text(
        '#include "native-loop.c"\n'
        'int main(void) { return merit_main(0, 3, 1) == 3 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    loop_program = tmp_path / "native-loop-program"
    subprocess.run([cc, "-std=c11", str(loop_driver), "-o", str(loop_program)],
                   check=True, capture_output=True)
    subprocess.run([str(loop_program)], check=True, capture_output=True)

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
