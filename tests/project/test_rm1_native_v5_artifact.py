"""Public native compiler produces an executable, strictly decoded RM1 v5 bundle."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import pytest

from merit.compiler import Checker, CompileError, parse
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.local_borrow_source_hir import lower_checked_local_borrow_source_hir
from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.resolved_source_function_bundle import decode_native_project_artifact_transport
from merit.project.build import build, interpret
from merit.project.loader import load_project
from merit.project.project_request import encode_loaded_project_request
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request
from merit.project.replacement import build_replacement_project
from merit.project.replacement_loader import load_replacement_project
from merit.project.replacement_prepare import (
    NativeReplacementDriver, ReplacementLocalBorrowError, prepare_replacement_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


def test_native_local_loan_diagnostic_span_transport_rejects_bad_framing() -> None:
    from merit.project.replacement_prepare import _native_local_loan_failure

    first = b"module a\nfn helper()->i32 { return 0; }\n"
    second = "module b\nfn main()->i32 { let café:i32=1; return café; }\n".encode("utf-8")
    request = encode_project_request(ProjectRequest(
        "probe", "src/b.mrt", (
            ProjectRequestUnit("src/a.mrt", first),
            ProjectRequestUnit("src/b.mrt", second),
        ),
    ))
    target = second.index("return café".encode("utf-8")) + len("return ")
    offset = len(b"module probe\n") + len(first) + target
    packet = [1297236550, 5, 0, 1296843847, 1, 5404, 2, offset, len("café".encode()), -1, 0]
    payload = ("\n".join(map(str, packet)) + "\n").encode()
    diagnostic = _native_local_loan_failure(payload, request)
    assert diagnostic is not None
    assert diagnostic.primary.path == "src/b.mrt"
    assert (diagnostic.primary.line, diagnostic.primary.column,
            diagnostic.primary.end_line, diagnostic.primary.end_column) == (2, 41, 2, 45)
    assert _native_local_loan_failure(payload + b"7\n", request) is None
    packet[7] = offset + len(second)
    assert _native_local_loan_failure(("\n".join(map(str, packet)) + "\n").encode(), request) is None


def test_rm1_native_v5_project_artifact_executes(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "compiler"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build", ".merit"))
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") +
                        '\n[executable]\nadapter = "stdin-string-i32"\n'
                        'entry = "emit_native_project_artifacts"\n',
                        encoding="utf-8", newline="\n")
    _, _, executable = build(load_project(manifest), tmp_path / "build" / "compiler")
    project = tmp_path / "input"
    (project / "src").mkdir(parents=True)
    (project / "Merit.toml").write_text(
        '[package]\nname = "probe"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n', encoding="utf-8", newline="\n")
    (project / "src/main.mrt").write_text(
        'module probe\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(r); return 0; }\n',
        encoding="utf-8", newline="\n")
    request = encode_loaded_project_request(load_project(project / "Merit.toml"))
    result = subprocess.run([str(executable)], input=request, capture_output=True)
    assert result.returncode == 0, (result.returncode, result.stderr.decode(errors="replace"))
    repeated = subprocess.run([str(executable)], input=request, capture_output=True)
    assert repeated.returncode == 0
    assert repeated.stdout == result.stdout
    transport = decode_native_project_artifact_transport(int(line) for line in result.stdout.splitlines())
    assert transport.version == 5
    assert parse_mir(json.loads(transport.canonical_mir_bytes)).schema == "bootstrap-mir-v2"
    reference_mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(
        (project / "src/main.mrt").read_text(encoding="utf-8")
    ))
    reference_bytes = canonical_mir_json(reference_mir).encode("utf-8")
    native_data = json.loads(transport.canonical_mir_bytes)
    oracle_data = json.loads(reference_bytes)
    # Project request preparation prefixes the effective source with its
    # canonical package module declaration; compare source-relative spans.
    prefix_length = len("module probe\n")
    for function in native_data["functions"]:
        for block in function["blocks"]:
            for instruction in block["instructions"]:
                if "span" in instruction:
                    instruction["span"][0] -= prefix_length
            if "span" in block["terminator"]:
                block["terminator"]["span"][0] -= prefix_length
        for effect in function["local_loan_effects"]:
            effect["span"][0] -= prefix_length
        for local in function["locals"]:
            if local["name"].startswith("_t"):
                local["name"] = f'_t{local["id"]}'
    for function in oracle_data["functions"]:
        for local in function["locals"]:
            if local["name"].startswith("_t"):
                local["name"] = f'_t{local["id"]}'
    if native_data != oracle_data:
        import difflib
        native_pretty = json.dumps(native_data, indent=2, sort_keys=True)
        oracle_pretty = json.dumps(oracle_data, indent=2, sort_keys=True)
        difference = "\n".join(difflib.unified_diff(
            oracle_pretty.splitlines(), native_pretty.splitlines(),
            fromfile="oracle", tofile="native", lineterm="",
        ))
        raise AssertionError(difference)
    generated = tmp_path / "generated.c"
    generated.write_bytes(transport.c_source_bytes)
    cc = os.environ.get("CC") or shutil.which("gcc") or shutil.which("cc")
    if cc is None and Path("C:/msys64/ucrt64/bin/gcc.exe").is_file():
        cc = "C:/msys64/ucrt64/bin/gcc.exe"
    assert cc is not None
    program = tmp_path / "generated-program.exe"
    env = os.environ.copy()
    env["PATH"] = str(Path(cc).parent) + os.pathsep + env.get("PATH", "")
    env["TEMP"] = env["TMP"] = str(tmp_path)
    compiled = subprocess.run([cc, "-std=c11", str(generated), "-o", str(program)],
                              capture_output=True, env=env)
    assert compiled.returncode == 0, compiled.stderr.decode(errors="replace")
    native_output = subprocess.run([str(program)], check=True, capture_output=True, env=env).stdout.decode()
    assert native_output.replace("\r\n", "\n") == interpret(load_project(project / "Merit.toml"))
    replacement = load_replacement_project(project / "Merit.toml")
    prepared = prepare_replacement_artifacts(replacement, NativeReplacementDriver(executable))
    assert json.loads(prepared.manifest_path.read_text(encoding="utf-8"))["producer_protocol"] == (
        "merit-project-request-v1/resolved-source-function-bundle-v5"
    )
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("TEMP", env["TEMP"])
    monkeypatch.setenv("TMP", env["TMP"])
    public_build = build_replacement_project(replacement, tmp_path / "public-build" / "program")
    public_output = subprocess.run([str(public_build.executable)], check=True,
                                   capture_output=True, env=env).stdout.decode()
    assert public_output.replace("\r\n", "\n") == native_output.replace("\r\n", "\n")
    (project / "src/main.mrt").write_text(
        'module probe\nfn main()->i32 { var x:i32=1; '
        'let r: borrow i32=borrow x; x=2; print(r); return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    unsupported_request = encode_loaded_project_request(load_project(project / "Merit.toml"))
    unsupported = subprocess.run([str(executable)], input=unsupported_request, capture_output=True)
    assert unsupported.returncode != 0
    assert b"replacement driver status 907" in unsupported.stderr
    assert b"1297236550" not in unsupported.stdout.splitlines()[3:]
    matrix = {
        "01": 'let x:String="a"; let r: borrow String=borrow x; print(r);',
        "02": 'let x:String="a"; let r: borrow String=borrow x; let s: borrow String=borrow x; print(r); print(s);',
        "three_shared": 'let x:i32=1; let a: borrow i32=borrow x; let b: borrow i32=borrow x; let c: borrow i32=borrow x; print(a); print(b); print(c);',
        "04": 'var x:i32=1; let r: borrow i32=borrow x; print(r); x=2;',
        "07": 'let x:Box=Box {value:1}; let r: borrow Box=borrow x; print(r.value); let y:Box=x; print(y.value);',
        "09": 'let x:String="a"; let r: borrow String=borrow x; print(r); drop(x);',
        "18": 'var x:i32=1; with capability io { let r: borrow i32=borrow x; print(r); } x=2;',
        "borrowed_call": 'let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r);',
        "24": 'let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r);',
        "later_function": 'let x:i32=1; let r: borrow i32=borrow x; print(r);',
    }
    for case, body in matrix.items():
        declarations = 'capability io;\n' if case == "18" else ('struct Box { value:i32; }\n' if case == "07" else "")
        leading_functions = ('fn inspect(borrow value:i32)->i32 { return value; }\n' if case == "24"
                             else ('fn helper()->i32 { return 1; }\n' if case == "later_function" else ""))
        trailing_functions = 'fn inspect(borrow value:i32)->i32 { return value; }\n' if case == "borrowed_call" else ""
        (project / "src/main.mrt").write_text(
            f'module probe\n{declarations}{leading_functions}fn main()->i32 {{ {body} return 0; }}\n{trailing_functions}',
            encoding="utf-8", newline="\n",
        )
        case_request = encode_loaded_project_request(load_project(project / "Merit.toml"))
        case_result = subprocess.run([str(executable)], input=case_request, capture_output=True)
        assert case_result.returncode == 0, (case, case_result.stderr.decode(errors="replace"))
        case_transport = decode_native_project_artifact_transport(
            int(line) for line in case_result.stdout.splitlines()
        )
        assert case_transport.version == 5
        case_mir = parse_mir(json.loads(case_transport.canonical_mir_bytes))
        assert case_mir.schema == "bootstrap-mir-v2"
        if case in {"01", "02", "07", "09"}:
            reference_case_mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(
                (project / "src/main.mrt").read_text(encoding="utf-8")
            ))
            native_effects = case_mir.functions[0].local_loan_effects
            reference_effects = reference_case_mir.functions[0].local_loan_effects
            assert [
                (effect.instruction_id, effect.kind, effect.reference_binding_id, effect.origin_binding_id)
                for effect in native_effects
            ] == [
                (effect.instruction_id, effect.kind, effect.reference_binding_id, effect.origin_binding_id)
                for effect in reference_effects
            ]
            if case in {"01", "09"}:
                assert [
                    (local.name, local.ownership)
                    for local in case_mir.functions[0].locals
                    if local.source_binding_id is not None
                ] == [
                    (local.name, local.ownership)
                    for local in reference_case_mir.functions[0].locals
                    if local.source_binding_id is not None
                ]
                assert [
                    (instruction.kind, instruction.ownership)
                    for block in case_mir.functions[0].blocks
                    for instruction in block.instructions
                ] == [
                    (instruction.kind, instruction.ownership)
                    for block in reference_case_mir.functions[0].blocks
                    for instruction in block.instructions
                ]
        case_c = tmp_path / f"case-{case}.c"
        case_c.write_bytes(case_transport.c_source_bytes)
        case_program = tmp_path / f"case-{case}.exe"
        case_compile = subprocess.run([cc, "-std=c11", str(case_c), "-o", str(case_program)],
                                      capture_output=True, env=env)
        assert case_compile.returncode == 0, case_compile.stderr.decode(errors="replace")
        observed = subprocess.run([str(case_program)], check=True, capture_output=True,
                                  env=env).stdout.decode().replace("\r\n", "\n")
        assert observed == interpret(load_project(project / "Merit.toml"))
    (project / "src/main.mrt").write_text(
        'module probe\nfn helper()->i32 { return 1; }\n'
        'fn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; '
        'x=2; print(r); return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    invalid_request = encode_loaded_project_request(load_project(project / "Merit.toml"))
    invalid = subprocess.run([str(executable)], input=invalid_request, capture_output=True)
    assert invalid.returncode != 0
    assert b"replacement driver status 907" in invalid.stderr
    assert b"1297236550" not in invalid.stdout.splitlines()[3:]
    rejected = {
        "05": ('var x:i32=1; let r: borrow i32=borrow x; x=2; print(r);', "", "M5402"),
        "06": ('let x:Box=Box {value:1}; let r: borrow Box=borrow x; let y:Box=x; print(r.value);',
               'struct Box { value:i32; }\n', "M5402"),
        "08": ('let x:String="a"; let r: borrow String=borrow x; drop(x); print(r);', "", "M5402"),
        "22": ('let x:i32=1; let r: borrow i32=borrow x; return r;', "", "M5404"),
        "23": ('let x:i32=1; let r: borrow i32=borrow x; let h:Holder=Holder {value:r};',
               'struct Holder { value:i32; }\n', "M5404"),
        "28": ('let x:String="a"; let r: borrow String=borrow x; replace(x,"b"); print(r);',
               "", "M5402"),
    }
    for case, (body, declarations, code) in rejected.items():
        source = f'module probe\n{declarations}fn main()->i32 {{ {body} return 0; }}\n'
        (project / "src/main.mrt").write_text(source, encoding="utf-8", newline="\n")
        try:
            Checker(parse(source)).check()
        except CompileError as error:
            assert error.code == code, case
            reference_error = error
        else:
            raise AssertionError(f"oracle accepted rejected case {case}")
        rejected_request = encode_loaded_project_request(load_project(project / "Merit.toml"))
        rejected_result = subprocess.run([str(executable)], input=rejected_request, capture_output=True)
        assert rejected_result.returncode != 0, case
        assert b"replacement driver status 907" in rejected_result.stderr, case
        rows = [int(line) for line in rejected_result.stdout.splitlines()]
        assert rows[:3] == [1297236550, 5, 0], case
        assert rows[3:5] == [1296843847, 1], (case, rows)
        assert rows[5] == int(code[1:]), (case, rows)
        assert len(rows) == 11, (case, rows)
        def source_offset(span) -> int:
            lines = source.splitlines(keepends=True)
            return (sum(len(line.encode("utf-8")) for line in lines[:span.line - 1])
                    + len(lines[span.line - 1][:span.column - 1].encode("utf-8")))

        primary = reference_error.span
        assert primary is not None
        assert rows[7] - len("module probe\n") == source_offset(primary), (case, rows, primary)
        assert rows[8] == source_offset(type(primary)(
            primary.end_line, primary.end_column, primary.end_line, primary.end_column,
            primary.source_name,
        )) - source_offset(primary), (case, rows, primary)
        if reference_error.notes:
            note_span = reference_error.notes[0].span
            assert note_span is not None
            assert rows[9] - len("module probe\n") == source_offset(note_span), (case, rows, note_span)
        else:
            assert rows[9:] == [-1, 0], (case, rows)
        with pytest.raises(ReplacementLocalBorrowError) as native_error:
            prepare_replacement_artifacts(
                load_replacement_project(project / "Merit.toml"), NativeReplacementDriver(executable)
            )
        assert native_error.value.code == code
        assert (native_error.value.primary.line, native_error.value.primary.column,
                native_error.value.primary.end_line, native_error.value.primary.end_column) == (
                    primary.line, primary.column, primary.end_line, primary.end_column
                ), case
        assert len(native_error.value.notes) == len(reference_error.notes), case
        if reference_error.notes:
            native_note = native_error.value.notes[0][1]
            oracle_note = reference_error.notes[0].span
            assert oracle_note is not None
            assert (native_note.line, native_note.column, native_note.end_line,
                    native_note.end_column) == (oracle_note.line, oracle_note.column,
                                         oracle_note.end_line, oracle_note.end_column), case
    (project / "src/main.mrt").write_text(
        'module probe\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; '
        'let y:i32=r; return 0; }\n', encoding="utf-8", newline="\n",
    )
    unclassified = subprocess.run(
        [str(executable)],
        input=encode_loaded_project_request(load_project(project / "Merit.toml")),
        capture_output=True,
    )
    assert unclassified.returncode != 0
    assert b"replacement driver status 907" in unclassified.stderr
    assert [int(line) for line in unclassified.stdout.splitlines()] == [1297236550, 5, 0]
