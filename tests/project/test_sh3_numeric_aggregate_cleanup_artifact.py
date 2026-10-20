"""SH3 recursive aggregate cleanup preserves exact-numeric Copy leaves."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from merit.bootstrap.mir_contract import parse_mir
from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
from merit.bootstrap.resolved_source_function_bundle import decode_native_project_artifact_transport
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None,
                    reason="C compiler unavailable")
def test_native_numeric_aggregate_cleanup_matches_oracle(tmp_path: Path) -> None:
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
        "decimal USD(18,2,half_even);\n"
        "bounded AccountId(u64,1,9999);\n"
        "struct Account { id:AccountId; balance:USD; }\n"
        "fn main()->i32 { let account:Account=Account { id:1, balance:1.00 }; "
        "drop(account); return 0; }\n"
    ).encode("utf-8")
    request = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt", (ProjectRequestUnit("src/main.mrt", source),),
        header_exports=(),
    ))
    completed = subprocess.run([str(executable)], input=request, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    artifact = decode_native_project_artifact_transport(
        int(line) for line in completed.stdout.splitlines()
    )
    module = parse_mir(json.loads(artifact.canonical_mir_bytes))
    assert artifact.c_source_bytes.decode("utf-8") == emit_c_module(module)
    assert artifact.c_header_bytes.decode("utf-8") == emit_c_header(module)
    generated = tmp_path / "numeric-aggregate.c"
    generated.write_bytes(artifact.c_source_bytes)
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    executable_path = tmp_path / "numeric-aggregate.exe"
    linked = subprocess.run(
        [compiler, "-std=c11", str(generated), "-o", str(executable_path)],
        capture_output=True, text=True,
    )
    assert linked.returncode == 0, linked.stderr
    run = subprocess.run([str(executable_path)], capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout == b""

    contract_source = (
        "module probe\n"
        "decimal USD(18,2,half_even);\n"
        "bounded AccountId(u64,1,9999);\n"
        "struct Account { id:AccountId; balance:USD; }\n"
        "fn deposit(borrow_mut account:Account, amount:USD)->USD\n"
        "requires amount > 0.00;\n"
        "requires account.id > 0;\n"
        "ensures result == old(account.balance) + amount;\n"
        "{ account.balance=checked_add(account.balance,amount); return account.balance; }\n"
        "fn main()->i32 { var account:Account=Account { id:1, balance:1.00 }; "
        "deposit(account,2.00); return 0; }\n"
    ).encode("utf-8")
    contract_request = encode_project_request(ProjectRequest(
        "probe", "src/main.mrt", (ProjectRequestUnit("src/main.mrt", contract_source),),
        header_exports=(),
    ))
    contract_completed = subprocess.run(
        [str(executable)], input=contract_request, capture_output=True,
    )
    assert contract_completed.returncode == 0, contract_completed.stderr.decode(
        "utf-8", errors="replace"
    )
    contract_artifact = decode_native_project_artifact_transport(
        int(line) for line in contract_completed.stdout.splitlines()
    )
    contract_module = parse_mir(json.loads(contract_artifact.canonical_mir_bytes))
    assert contract_artifact.c_source_bytes.decode("utf-8") == emit_c_module(contract_module)
    assert contract_artifact.c_header_bytes.decode("utf-8") == emit_c_header(contract_module)
    contract_c = tmp_path / "numeric-contract.c"
    contract_c.write_bytes(contract_artifact.c_source_bytes)
    contract_executable = tmp_path / "numeric-contract.exe"
    contract_linked = subprocess.run(
        [compiler, "-std=c11", str(contract_c), "-o", str(contract_executable)],
        capture_output=True, text=True,
    )
    assert contract_linked.returncode == 0, contract_linked.stderr
    contract_run = subprocess.run([str(contract_executable)], capture_output=True)
    assert contract_run.returncode == 0, contract_run.stderr
    assert contract_run.stdout == b""
