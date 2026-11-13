"""Public native compiler produces an executable, strictly decoded RM1 v5 bundle."""

from pathlib import Path
import json
import os
import shutil
import subprocess

from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.local_borrow_source_hir import lower_checked_local_borrow_source_hir
from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.resolved_source_function_bundle import decode_native_project_artifact_transport
from merit.project.build import build, interpret
from merit.project.loader import load_project
from merit.project.project_request import encode_loaded_project_request
from merit.project.replacement import build_replacement_project
from merit.project.replacement_loader import load_replacement_project
from merit.project.replacement_prepare import NativeReplacementDriver, prepare_replacement_artifacts


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


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
        'module probe\nfn main()->i32 { let x:i32=1; '
        'let r: borrow i32=borrow x; let s: borrow i32=borrow x; '
        'print(r); print(s); return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    unsupported_request = encode_loaded_project_request(load_project(project / "Merit.toml"))
    unsupported = subprocess.run([str(executable)], input=unsupported_request, capture_output=True)
    assert unsupported.returncode != 0
    assert b"replacement driver status 907" in unsupported.stderr
    assert b"1297236550" not in unsupported.stdout.splitlines()[3:]
    matrix = {
        "01": 'let x:String="a"; let r: borrow String=borrow x; print(r);',
        "04": 'var x:i32=1; let r: borrow i32=borrow x; print(r); x=2;',
        "18": 'var x:i32=1; with capability io { let r: borrow i32=borrow x; print(r); } x=2;',
        "borrowed_call": 'let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r);',
    }
    for case, body in matrix.items():
        declarations = 'capability io;\n' if case == "18" else ""
        trailing_functions = 'fn inspect(borrow value:i32)->i32 { return value; }\n' if case == "borrowed_call" else ""
        (project / "src/main.mrt").write_text(
            f'module probe\n{declarations}fn main()->i32 {{ {body} return 0; }}\n{trailing_functions}',
            encoding="utf-8", newline="\n",
        )
        case_request = encode_loaded_project_request(load_project(project / "Merit.toml"))
        case_result = subprocess.run([str(executable)], input=case_request, capture_output=True)
        assert case_result.returncode == 0, (case, case_result.stderr.decode(errors="replace"))
        case_transport = decode_native_project_artifact_transport(
            int(line) for line in case_result.stdout.splitlines()
        )
        assert case_transport.version == 5
        assert parse_mir(json.loads(case_transport.canonical_mir_bytes)).schema == "bootstrap-mir-v2"
        case_c = tmp_path / f"case-{case}.c"
        case_c.write_bytes(case_transport.c_source_bytes)
        case_program = tmp_path / f"case-{case}.exe"
        case_compile = subprocess.run([cc, "-std=c11", str(case_c), "-o", str(case_program)],
                                      capture_output=True, env=env)
        assert case_compile.returncode == 0, case_compile.stderr.decode(errors="replace")
        observed = subprocess.run([str(case_program)], check=True, capture_output=True,
                                  env=env).stdout.decode().replace("\r\n", "\n")
        assert observed == interpret(load_project(project / "Merit.toml"))
