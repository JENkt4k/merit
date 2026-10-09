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
from merit.bootstrap.replacement_project import ReplacementFunctionInput, build_replacement_project_artifact
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
        "module probe\n"
        "fn identity(value:i64)->i64 { return value; }\n"
        "pub fn main()->i32 { print(identity(9)); return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    identity_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    identity_completed = subprocess.run([str(executable)], input=identity_request, capture_output=True)
    assert identity_completed.returncode == 0, identity_completed.stderr.decode("utf-8", errors="replace")
    identity_transport = decode_native_project_artifact_transport(
        int(line) for line in identity_completed.stdout.splitlines()
    )
    identity_mir = parse_mir(json.loads(identity_transport.canonical_mir_bytes))
    assert identity_transport.c_source_bytes.decode("utf-8") == emit_c_module(identity_mir)
    assert identity_transport.c_header_bytes.decode("utf-8") == emit_c_header(identity_mir)

    generic_request = encode_loaded_project_request(load_project(
        repository / "examples" / "projects" / "generic_result" / "Merit.toml"
    ))
    generic_completed = subprocess.run([str(executable)], input=generic_request, capture_output=True)
    assert generic_completed.returncode == 0, generic_completed.stderr.decode("utf-8", errors="replace")
    generic_transport = decode_native_project_artifact_transport(
        int(line) for line in generic_completed.stdout.splitlines()
    )
    generic_mir = parse_mir(json.loads(generic_transport.canonical_mir_bytes))
    assert generic_transport.c_source_bytes.decode("utf-8") == emit_c_module(generic_mir)
    assert generic_transport.c_header_bytes.decode("utf-8") == emit_c_header(generic_mir)
    generic_c = tmp_path / "native-generic-result.c"
    generic_c.write_bytes(generic_transport.c_source_bytes)
    generic_program = tmp_path / "native-generic-result-program"
    subprocess.run([cc, "-std=c11", str(generic_c), "-o", str(generic_program)],
                   check=True, capture_output=True)
    assert subprocess.run([str(generic_program)], check=True, capture_output=True).stdout.splitlines() == [
        b"42", b"42"
    ]

    trait_request = encode_loaded_project_request(load_project(
        repository / "examples" / "projects" / "trait_bounds" / "Merit.toml"
    ))
    trait_completed = subprocess.run([str(executable)], input=trait_request, capture_output=True)
    assert trait_completed.returncode == 0, trait_completed.stderr.decode("utf-8", errors="replace")
    trait_transport = decode_native_project_artifact_transport(
        int(line) for line in trait_completed.stdout.splitlines()
    )
    trait_mir = parse_mir(json.loads(trait_transport.canonical_mir_bytes))
    assert trait_transport.c_source_bytes.decode("utf-8") == emit_c_module(trait_mir)
    assert trait_transport.c_header_bytes.decode("utf-8") == emit_c_header(trait_mir)
    trait_c = tmp_path / "native-trait-bounds.c"
    trait_c.write_bytes(trait_transport.c_source_bytes)
    trait_program = tmp_path / "native-trait-bounds-program"
    subprocess.run([cc, "-std=c11", str(trait_c), "-o", str(trait_program)],
                   check=True, capture_output=True)
    assert subprocess.run([str(trait_program)], check=True, capture_output=True).stdout.splitlines() == [b"17"]

    views_request = encode_loaded_project_request(load_project(
        repository / "examples" / "projects" / "borrowed_views" / "Merit.toml"
    ))
    views_completed = subprocess.run([str(executable)], input=views_request, capture_output=True)
    assert views_completed.returncode == 0, views_completed.stderr.decode("utf-8", errors="replace")
    views_transport = decode_native_project_artifact_transport(
        int(line) for line in views_completed.stdout.splitlines()
    )
    views_mir = parse_mir(json.loads(views_transport.canonical_mir_bytes))
    assert views_transport.c_source_bytes.decode("utf-8") == emit_c_module(views_mir)
    assert views_transport.c_header_bytes.decode("utf-8") == emit_c_header(views_mir)
    views_c = tmp_path / "native-borrowed-views.c"
    views_c.write_bytes(views_transport.c_source_bytes)
    views_program = tmp_path / "native-borrowed-views-program"
    subprocess.run([cc, "-std=c11", str(views_c), "-o", str(views_program)],
                   check=True, capture_output=True)
    assert subprocess.run([str(views_program)], check=True, capture_output=True).stdout.splitlines() == [
        b"5", b"8"
    ]
    views_h = tmp_path / "native-borrowed-views.h"
    views_h.write_bytes(views_transport.c_header_bytes)
    views_abi_probe = tmp_path / "native-borrowed-views-abi.c"
    views_abi_probe.write_text(
        '#include "native-borrowed-views.h"\n'
        'int merit_abi_probe(merit_Record *value) {\n'
        '    return merit_edit_record(value)->number;\n'
        '}\n',
        encoding="utf-8", newline="\n",
    )
    subprocess.run([cc, "-std=c11", "-c", str(views_abi_probe),
                    "-o", str(tmp_path / "native-borrowed-views-abi.o")],
                   check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\n'
        'pub stable("v1") struct Inner { x:i8; y:i32; }\n'
        'pub stable("v1") struct Outer { inner:Inner; z:i16; }\n'
        'pub fn view(borrow value:Outer)->borrow Outer { return value; }\n'
        'pub fn main()->i32 { return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    stable_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    stable_completed = subprocess.run([str(executable)], input=stable_request, capture_output=True)
    assert stable_completed.returncode == 0, stable_completed.stderr.decode("utf-8", errors="replace")
    stable_transport = decode_native_project_artifact_transport(
        int(line) for line in stable_completed.stdout.splitlines()
    )
    stable_mir = parse_mir(json.loads(stable_transport.canonical_mir_bytes))
    assert stable_transport.c_header_bytes.decode("utf-8") == emit_c_header(stable_mir)
    assert b"offsetof(merit_Inner, y) == 4" in stable_transport.c_header_bytes
    assert b"sizeof(merit_Outer) == 12" in stable_transport.c_header_bytes

    (source_root / "src" / "main.mrt").write_text(
        "module probe\n"
        "fn choose(left:i64,right:i64)->i64 { "
        "if (left >= right) { return left; } else { return right; } }\n"
        "pub fn main()->i32 { print(choose(7,3)); return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    branch_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    branch_completed = subprocess.run([str(executable)], input=branch_request, capture_output=True)
    assert branch_completed.returncode == 0, branch_completed.stderr.decode("utf-8", errors="replace")
    branch_transport = decode_native_project_artifact_transport(
        int(line) for line in branch_completed.stdout.splitlines()
    )
    branch_mir = parse_mir(json.loads(branch_transport.canonical_mir_bytes))
    assert branch_transport.c_source_bytes.decode("utf-8") == emit_c_module(branch_mir)
    assert branch_transport.c_header_bytes.decode("utf-8") == emit_c_header(branch_mir)
    branch_c = tmp_path / "native-branch.c"
    branch_c.write_bytes(branch_transport.c_source_bytes)
    branch_driver = tmp_path / "native-branch-driver.c"
    branch_driver.write_text(
        '#include "native-branch.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    branch_program = tmp_path / "native-branch-program"
    subprocess.run([cc, "-std=c11", str(branch_driver), "-o", str(branch_program)],
                   check=True, capture_output=True)
    assert subprocess.run([str(branch_program)], check=True, capture_output=True).stdout.splitlines() == [b"7"]

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
        'module probe\nstable("v1") struct Point { x:i32; }\n'
        'pub fn main()->i32 { let p:Point=Point { x:17 }; return p.x; }\n',
        encoding="utf-8", newline="\n",
    )
    aggregate_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    aggregate_result = subprocess.run([str(executable)], input=aggregate_request,
                                      capture_output=True)
    assert aggregate_result.returncode == 0, aggregate_result.stderr.decode("utf-8", errors="replace")
    aggregate_transport = decode_native_project_artifact_transport(
        int(line) for line in aggregate_result.stdout.splitlines()
    )
    aggregate_mir = parse_mir(json.loads(aggregate_transport.canonical_mir_bytes))
    assert aggregate_transport.c_source_bytes.decode("utf-8") == emit_c_module(aggregate_mir)
    assert aggregate_transport.c_header_bytes.decode("utf-8") == emit_c_header(aggregate_mir)
    aggregate_c = tmp_path / "native-aggregate.c"
    aggregate_c.write_bytes(aggregate_transport.c_source_bytes)
    aggregate_driver = tmp_path / "native-aggregate-driver.c"
    aggregate_driver.write_text(
        '#include "native-aggregate.c"\n'
        'int main(void) { return merit_main() == 17 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    aggregate_program = tmp_path / "native-aggregate-program"
    subprocess.run([cc, "-std=c11", str(aggregate_driver), "-o", str(aggregate_program)],
                   check=True, capture_output=True)
    subprocess.run([str(aggregate_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nstruct Inner { x:i32; y:i32; }\nstruct Outer { inner:Inner; }\n'
        'pub fn main()->i32 { let inner:Inner=Inner { x:23, y:0 }; '
        'let outer:Outer=Outer { inner:inner }; return outer.inner.x; }\n',
        encoding="utf-8", newline="\n",
    )
    nested_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    nested_result = subprocess.run([str(executable)], input=nested_request, capture_output=True)
    assert nested_result.returncode == 0, nested_result.stderr.decode("utf-8", errors="replace")
    nested_transport = decode_native_project_artifact_transport(
        int(line) for line in nested_result.stdout.splitlines()
    )
    nested_mir = parse_mir(json.loads(nested_transport.canonical_mir_bytes))
    assert nested_transport.c_source_bytes.decode("utf-8") == emit_c_module(nested_mir)
    assert nested_transport.c_header_bytes.decode("utf-8") == emit_c_header(nested_mir)
    nested_c = tmp_path / "native-nested-aggregate.c"
    nested_c.write_bytes(nested_transport.c_source_bytes)
    nested_driver = tmp_path / "native-nested-aggregate-driver.c"
    nested_driver.write_text(
        '#include "native-nested-aggregate.c"\n'
        'int main(void) { return merit_main() == 23 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    nested_program = tmp_path / "native-nested-aggregate-program"
    subprocess.run([cc, "-std=c11", str(nested_driver), "-o", str(nested_program)],
                   check=True, capture_output=True)
    subprocess.run([str(nested_program)], check=True, capture_output=True)

    (source_root / "src" / "main.mrt").write_text(
        'module probe\ncapability allocate;\n'
        'fn take_allocator(allocator:Allocator)->i32 { return 11; }\n'
        'pub fn main()->i32 { with capability allocate { '
        'let allocator:Allocator=system_allocator(); '
        'let value:i32=take_allocator(allocator); print(value); } return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    allocator_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    allocator_result = subprocess.run([str(executable)], input=allocator_request,
                                      capture_output=True)
    assert allocator_result.returncode == 0, allocator_result.stderr.decode("utf-8", errors="replace")
    allocator_transport = decode_native_project_artifact_transport(
        int(line) for line in allocator_result.stdout.splitlines()
    )
    allocator_mir = parse_mir(json.loads(allocator_transport.canonical_mir_bytes))
    assert allocator_transport.c_source_bytes.decode("utf-8") == emit_c_module(allocator_mir)
    assert allocator_transport.c_header_bytes.decode("utf-8") == emit_c_header(allocator_mir)
    allocator_c = tmp_path / "native-allocator-call.c"
    allocator_c.write_bytes(allocator_transport.c_source_bytes)
    allocator_driver = tmp_path / "native-allocator-call-driver.c"
    allocator_driver.write_text(
        '#include "native-allocator-call.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    allocator_program = tmp_path / "native-allocator-call-program"
    subprocess.run([cc, "-std=c11", str(allocator_driver), "-o", str(allocator_program)],
                   check=True, capture_output=True)
    allocator_output = subprocess.run([str(allocator_program)], check=True,
                                      capture_output=True).stdout
    assert allocator_output.replace(b"\r\n", b"\n") == b"11\n"

    (source_root / "src" / "main.mrt").write_text(
        'module probe\ncapability allocate;\n'
        'pub fn main()->i32 { with capability allocate { '
        'let allocator:Allocator=system_allocator(); '
        'var values:Vec<i64>=vec_new<i64>(allocator,1); '
        'vec_push<i64>(values,7); print(vec_len<i64>(values)); '
        'drop(values); } return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    vector_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    vector_result = subprocess.run([str(executable)], input=vector_request, capture_output=True)
    assert vector_result.returncode == 0, vector_result.stderr.decode("utf-8", errors="replace")
    vector_transport = decode_native_project_artifact_transport(
        int(line) for line in vector_result.stdout.splitlines()
    )
    vector_mir = parse_mir(json.loads(vector_transport.canonical_mir_bytes))
    assert vector_transport.c_source_bytes.decode("utf-8") == emit_c_module(vector_mir)
    assert vector_transport.c_header_bytes.decode("utf-8") == emit_c_header(vector_mir)
    vector_c = tmp_path / "native-vector-drop-call.c"
    vector_c.write_bytes(vector_transport.c_source_bytes)
    vector_driver = tmp_path / "native-vector-drop-call-driver.c"
    vector_driver.write_text(
        '#include "native-vector-drop-call.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    vector_program = tmp_path / "native-vector-drop-call-program"
    subprocess.run([cc, "-std=c11", str(vector_driver), "-o", str(vector_program)],
                   check=True, capture_output=True)
    vector_output = subprocess.run([str(vector_program)], check=True,
                                   capture_output=True).stdout
    assert vector_output.replace(b"\r\n", b"\n") == b"1\n"

    (source_root / "src" / "main.mrt").write_text(
        'module probe\nenum Choice { Some(i64), None }\n'
        'pub fn main()->i32 { let choice:Choice=Some(7); '
        'match(choice) { Some(value) => { print(value); } '
        'None => { print(0); } } return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    enum_request = encode_loaded_project_request(load_project(source_root / "Merit.toml"))
    enum_result = subprocess.run([str(executable)], input=enum_request, capture_output=True)
    assert enum_result.returncode == 0, enum_result.stderr.decode("utf-8", errors="replace")
    enum_transport = decode_native_project_artifact_transport(
        int(line) for line in enum_result.stdout.splitlines()
    )
    enum_mir = parse_mir(json.loads(enum_transport.canonical_mir_bytes))
    assert enum_transport.c_source_bytes.decode("utf-8") == emit_c_module(enum_mir)
    assert enum_transport.c_header_bytes.decode("utf-8") == emit_c_header(enum_mir)
    enum_c = tmp_path / "native-copy-enum.c"
    enum_c.write_bytes(enum_transport.c_source_bytes)
    enum_driver = tmp_path / "native-copy-enum-driver.c"
    enum_driver.write_text(
        '#include "native-copy-enum.c"\n'
        'int main(void) { return merit_main(); }\n',
        encoding="utf-8", newline="\n",
    )
    enum_program = tmp_path / "native-copy-enum-program"
    subprocess.run([cc, "-std=c11", str(enum_driver), "-o", str(enum_program)],
                   check=True, capture_output=True)
    enum_output = subprocess.run([str(enum_program)], check=True, capture_output=True).stdout
    assert enum_output.replace(b"\r\n", b"\n") == b"7\n"

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

    legacy_generic = subprocess.run([str(legacy_executable)], input=generic_request, capture_output=True)
    assert legacy_generic.returncode == 0, legacy_generic.stderr.decode("utf-8", errors="replace")
    generic_snapshots = decode_resolved_source_function_bundle(
        int(line) for line in legacy_generic.stdout.splitlines()
    )
    assert len(generic_snapshots.functions) == 3
    generic_source = bytes(generic_snapshots.functions[0].effective_source_bytes).decode("utf-8")
    generic_oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=generic_source,
                module_name=generic_snapshots.module_name,
                snapshot_values=values,
                capability_names={index + 1: name for index, name in enumerate(generic_snapshots.capability_names)},
            )
            for values in generic_snapshots.encoded_snapshots
        ),
        module_name=generic_snapshots.module_name,
    )
    assert generic_transport.canonical_mir_bytes == canonical_mir_json(generic_oracle.module).encode("utf-8")

    legacy_trait = subprocess.run([str(legacy_executable)], input=trait_request, capture_output=True)
    assert legacy_trait.returncode == 0, legacy_trait.stderr.decode("utf-8", errors="replace")
    trait_snapshots = decode_resolved_source_function_bundle(
        int(line) for line in legacy_trait.stdout.splitlines()
    )
    trait_source = bytes(trait_snapshots.functions[0].effective_source_bytes).decode("utf-8")
    trait_oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=trait_source,
                module_name=trait_snapshots.module_name,
                snapshot_values=values,
                capability_names={index + 1: name for index, name in enumerate(trait_snapshots.capability_names)},
            )
            for values in trait_snapshots.encoded_snapshots
        ),
        module_name=trait_snapshots.module_name,
    )
    assert trait_transport.canonical_mir_bytes == canonical_mir_json(trait_oracle.module).encode("utf-8")

    legacy_views = subprocess.run([str(legacy_executable)], input=views_request, capture_output=True)
    assert legacy_views.returncode == 0, legacy_views.stderr.decode("utf-8", errors="replace")
    views_snapshots = decode_resolved_source_function_bundle(
        int(line) for line in legacy_views.stdout.splitlines()
    )
    views_source = bytes(views_snapshots.functions[0].effective_source_bytes).decode("utf-8")
    views_oracle = build_replacement_project_artifact(
        (
            ReplacementFunctionInput.from_values(
                source=views_source,
                module_name=views_snapshots.module_name,
                snapshot_values=values,
                capability_names={index + 1: name for index, name in enumerate(views_snapshots.capability_names)},
            )
            for values in views_snapshots.encoded_snapshots
        ),
        module_name=views_snapshots.module_name,
    )
    assert views_transport.canonical_mir_bytes == canonical_mir_json(views_oracle.module).encode("utf-8")
