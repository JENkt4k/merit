"""Run fixed corpus and acceptance projects through the SH3 native-v4 path."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from merit.bootstrap.mir_contract import parse_mir
from merit.bootstrap.mir_to_c import MirToCError, emit_c_header
from merit.compiler import CompileError
from merit.project.build import build, build_shared, check
from merit.project.cli import main as project_cli_main
from merit.project.loader import ProjectError, load_project
from merit.project.project_request import ProjectRequest, ProjectRequestUnit, encode_project_request
from merit.project.replacement import (
    REPLACEMENT_MANIFEST, ReplacementProjectError, build_replacement_project,
    build_replacement_shared,
)
from merit.project.replacement_prepare import NativeReplacementDriver, prepare_replacement_artifacts


ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads((ROOT / "tests/project/alpha1_corpus_v1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native_v4_driver(tmp_path_factory: pytest.TempPathFactory) -> NativeReplacementDriver:
    if not any(shutil.which(name) for name in ("cc", "gcc", "clang")):
        pytest.skip("C compiler unavailable")

    temporary = tmp_path_factory.mktemp("sh3-v4-corpus-compiler")
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
    _, _, executable = build(load_project(manifest), temporary / "native-v4-compiler")
    return NativeReplacementDriver(executable)


def _write_case(root: Path, case: dict[str, object]) -> Path:
    root.mkdir()
    for relative, source in dict(case["files"]).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(source), encoding="utf-8", newline="\n")
    manifest = root / "Merit.toml"
    manifest.write_text(
        '[package]\n'
        f'name="alpha1_{str(case["id"]).replace("-", "_")}"\n'
        'entry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    return manifest


def _result(executable: Path, *, cwd: Path | None = None) -> tuple[int, bytes, bytes]:
    completed = subprocess.run([str(executable)], cwd=cwd, capture_output=True, timeout=30)
    return completed.returncode, completed.stdout, completed.stderr


@pytest.mark.parametrize("case", CORPUS["accepted"], ids=lambda case: case["id"])
def test_sh3_v4_accepts_complete_alpha1_corpus(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, case: dict[str, object],
) -> None:
    manifest = _write_case(tmp_path / str(case["id"]), case)
    project = load_project(manifest)
    check(project)
    _, _, reference = build(project, tmp_path / "reference")
    expected = _result(reference)
    assert expected[0] == 0, expected

    prepared = prepare_replacement_artifacts(project, native_v4_driver)
    assert len(prepared.project_artifact_paths) == 3
    first_publication = (
        prepared.manifest_path.read_bytes(),
        tuple(path.read_bytes() for path in prepared.project_artifact_paths),
    )
    repeated = prepare_replacement_artifacts(project, native_v4_driver)
    assert (
        repeated.manifest_path.read_bytes(),
        tuple(path.read_bytes() for path in repeated.project_artifact_paths),
    ) == first_publication
    artifact = build_replacement_project(project, tmp_path / "native-v4")
    assert _result(artifact.executable) == expected


@pytest.mark.parametrize("case", CORPUS["rejected"], ids=lambda case: case["id"])
def test_sh3_v4_rejects_complete_alpha1_corpus(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, case: dict[str, object],
) -> None:
    manifest = _write_case(tmp_path / str(case["id"]), case)
    try:
        project = load_project(manifest)
    except (ProjectError, CompileError, ValueError):
        assert case["id"] in {
            "wrong-generic-arity", "missing-trait-implementation",
            "private-qualified-call", "unimported-qualified-call",
        }
        units = tuple(
            ProjectRequestUnit(path, str(source).encode("utf-8"))
            for path, source in sorted(dict(case["files"]).items())
        )
        request = encode_project_request(ProjectRequest(
            manifest.parent.name.replace("-", "_"), "src/main.mrt", units,
            header_exports=(),
        ))
        response = subprocess.run(
            [str(native_v4_driver.executable)], input=request, capture_output=True,
        )
        assert response.returncode != 0, case["id"]
        assert b"replacement driver status" in response.stderr
        return
    with pytest.raises((ProjectError, CompileError, ValueError)):
        check(project)

    def rejection() -> tuple[str, str, str]:
        try:
            prepare_replacement_artifacts(project, native_v4_driver)
        except (ProjectError, CompileError, ReplacementProjectError, ValueError) as exc:
            assert not (manifest.parent / ".merit" / REPLACEMENT_MANIFEST).exists()
            return "prepare", type(exc).__name__, str(exc)
        try:
            build_replacement_project(project, tmp_path / "rejected-v4")
        except (ProjectError, CompileError, ReplacementProjectError, ValueError) as exc:
            return "build", type(exc).__name__, str(exc)
        pytest.fail("native-v4 compiler accepted a rejected Alpha.1 corpus case")

    first = rejection()
    assert first[0] == "prepare", (case["id"], first)
    assert rejection() == first


def test_sh3_v4_rejects_missing_import_without_python_loader(
    native_v4_driver: NativeReplacementDriver,
) -> None:
    request = encode_project_request(ProjectRequest(
        "missing_import", "src/main.mrt",
        (ProjectRequestUnit(
            "src/main.mrt",
            b"module main\nimport absent;\nfn main()->i32 { return 0; }\n",
        ),), header_exports=(),
    ))
    response = subprocess.run(
        [str(native_v4_driver.executable)], input=request, capture_output=True,
    )
    assert response.returncode != 0
    assert b"replacement driver status" in response.stderr


def test_sh3_v4_rejects_duplicate_module_without_python_loader(
    native_v4_driver: NativeReplacementDriver,
) -> None:
    request = encode_project_request(ProjectRequest(
        "duplicate_module", "src/main.mrt", (
            ProjectRequestUnit("src/library.mrt", b"module repeated\nfn helper()->i32 { return 1; }\n"),
            ProjectRequestUnit("src/main.mrt", b"module repeated\nfn main()->i32 { return 0; }\n"),
        ), header_exports=(),
    ))
    response = subprocess.run(
        [str(native_v4_driver.executable)], input=request, capture_output=True,
    )
    assert response.returncode != 0
    assert b"replacement driver status" in response.stderr


@pytest.mark.parametrize(("case_name", "library", "entry_source"), [
    (
        "import-cycle",
        b"module library\nimport main;\nfn helper()->i32 { return 1; }\n",
        b"module main\nimport library;\nfn main()->i32 { return library.helper(); }\n",
    ),
    (
        "duplicate-function",
        b"module library\nfn clash()->i32 { return 1; }\n",
        b"module main\nfn clash()->i32 { return 2; }\nfn main()->i32 { return 0; }\n",
    ),
    (
        "duplicate-type",
        b"module library\nstruct Item { value:i32; }\n",
        b"module main\nstruct Item { value:i32; }\nfn main()->i32 { return 0; }\n",
    ),
    (
        "nonentry-main",
        b"module library\nfn main()->i32 { return 1; }\n",
        b"module main\nfn run()->i32 { return 0; }\n",
    ),
])
def test_sh3_v4_rejects_invalid_cross_module_catalog_without_python_loader(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
    case_name: str, library: bytes, entry_source: bytes,
) -> None:
    manifest = _write_case(tmp_path / case_name, {
        "id": case_name,
        "files": {
            "src/library.mrt": library.decode("utf-8"),
            "src/main.mrt": entry_source.decode("utf-8"),
        },
    })
    with pytest.raises((ProjectError, CompileError)):
        load_project(manifest)
    request = encode_project_request(ProjectRequest(
        case_name.replace("-", "_"), "src/main.mrt", (
            ProjectRequestUnit("src/library.mrt", library),
            ProjectRequestUnit("src/main.mrt", entry_source),
        ), header_exports=(),
    ))
    response = subprocess.run(
        [str(native_v4_driver.executable)], input=request, capture_output=True,
    )
    assert response.returncode != 0, case_name
    assert b"replacement driver status" in response.stderr


@pytest.mark.parametrize("name, side_effect", [
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
def test_sh3_v4_acceptance_project_builds_through_production_path(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
    name: str, side_effect: str | None,
) -> None:
    project_root = tmp_path / name
    shutil.copytree(ROOT / "examples/projects" / name, project_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    project = load_project(project_root / "Merit.toml")
    _, _, reference = build(project, tmp_path / "reference")
    native_output = tmp_path / "native-v4"
    assert project_cli_main([
        "build", str(project_root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(native_output),
    ]) == 0
    manifest = json.loads((project_root / ".merit" / REPLACEMENT_MANIFEST).read_text(
        encoding="utf-8"
    ))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v2/resolved-source-function-bundle-v4"
    )
    assert set(manifest["native_artifacts"]) == {"canonical_mir", "c_source", "c_header"}
    native_executable = native_output.with_suffix(".exe") if os.name == "nt" else native_output

    reference_directory = tmp_path / "reference-run"
    native_directory = tmp_path / "native-run"
    reference_directory.mkdir()
    native_directory.mkdir()
    expected = _result(reference, cwd=reference_directory)
    actual = _result(native_executable, cwd=native_directory)
    assert expected[0] == 0, expected
    assert actual == expected
    if side_effect is not None:
        assert (native_directory / side_effect).read_bytes() == (
            reference_directory / side_effect
        ).read_bytes()


def test_sh3_v4_public_check_shared_and_run_keep_explicit_empty_exports(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    project_root = tmp_path / "generic_result"
    shutil.copytree(ROOT / "examples/projects/generic_result", project_root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    driver = str(native_v4_driver.executable)
    assert project_cli_main(["check", str(project_root), "--compiler-path", driver]) == 0
    assert project_cli_main([
        "build-shared", str(project_root), "--compiler-path", driver,
        "-o", str(tmp_path / "native-shared"),
    ]) == 0
    assert project_cli_main([
        "run", str(project_root), "--compiler-path", driver,
        "-o", str(tmp_path / "native-run"),
    ]) == 0
    manifest = json.loads((project_root / ".merit" / REPLACEMENT_MANIFEST).read_text(
        encoding="utf-8"
    ))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v2/resolved-source-function-bundle-v4"
    )


def test_sh3_v4_public_shared_build_selects_only_manifest_entry(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "selected"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="selected"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n\n'
        '[executable]\nadapter="stdin-string-i32"\nentry="selected"\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module selected\n'
        'pub fn selected(source:String)->i32 { return 0; }\n'
        'pub fn omitted()->i32 { return 1; }\n',
        encoding="utf-8", newline="\n",
    )
    output = tmp_path / "selected-library"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_text(encoding="utf-8")
    assert "merit_selected" in header
    assert "merit_omitted" not in header
    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    library = ctypes.CDLL(str(output.with_suffix(suffix)))

    class MeritString(ctypes.Structure):
        _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("len", ctypes.c_size_t)]

    selected = library.merit_selected
    selected.argtypes = [MeritString]
    selected.restype = ctypes.c_int32
    text = (ctypes.c_uint8 * 3)(97, 98, 99)
    assert selected(MeritString(text, 3)) == 0
    manifest = json.loads((root / ".merit" / REPLACEMENT_MANIFEST).read_text(
        encoding="utf-8"
    ))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v2/resolved-source-function-bundle-v4"
    )


@pytest.mark.parametrize("entry", ["private_entry", "missing_entry"])
def test_sh3_v4_public_shared_build_rejects_unexportable_entry(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, entry: str,
) -> None:
    root = tmp_path / entry
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="unexportable"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n\n'
        f'[executable]\nadapter="stdin-string-i32"\nentry="{entry}"\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module unexportable\n'
        'fn private_entry(source:String)->i32 { return 0; }\n'
        'pub fn available(source:String)->i32 { return 1; }\n',
        encoding="utf-8", newline="\n",
    )
    output = tmp_path / "unexportable-library"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) != 0
    assert not (root / ".merit" / REPLACEMENT_MANIFEST).exists()
    assert not output.with_suffix(".h").exists()


def test_sh3_v4_public_shared_build_preserves_stable_struct_abi(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "shared_struct_api"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="shared_struct_api"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module shared_struct_api\n'
        'pub stable("point-v1") struct Point { x:i32; y:i32; }\n'
        'pub fn point_sum(point:Point)->i32 { return checked_add(point.x,point.y); }\n'
        'fn main()->i32 { return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    assert project_cli_main([
        "build", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(tmp_path / "plain-executable"),
    ]) == 0
    with pytest.raises(ReplacementProjectError, match="missing or incompatible"):
        build_replacement_shared(
            load_project(root / "Merit.toml"), tmp_path / "stale-empty-header",
        )
    output = tmp_path / "shared_struct_api"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_text(encoding="utf-8")
    assert "merit_point_sum" in header
    assert "sizeof(merit_Point) == 8" in header
    manifest = json.loads((root / ".merit" / REPLACEMENT_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["producer_protocol"] == (
        "merit-project-request-v1/resolved-source-function-bundle-v4"
    )

    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]

    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    library = ctypes.CDLL(str(output.with_suffix(suffix)))
    point_sum = library.merit_point_sum
    point_sum.argtypes = [Point]
    point_sum.restype = ctypes.c_int32
    assert point_sum(Point(19, 23)) == 42


def test_sh3_v4_public_shared_build_preserves_ledger_decimal_abi(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "ledger_app"
    shutil.copytree(ROOT / "examples/projects/ledger_app", root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    project = load_project(root / "Merit.toml")
    _, oracle_header, _ = build_shared(project, tmp_path / "reference-ledger")

    output = tmp_path / "native-ledger"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_bytes()
    reference_header = oracle_header.read_bytes()
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    assert header == emit_c_header(module).encode("utf-8")
    for contract in (
        b"sizeof(merit_Account) == 16",
        b"__builtin_offsetof(merit_Account, balance) == 8",
        b"int64_t merit_deposit(merit_Account *account, int64_t amount);",
        b"int64_t merit_account_balance(const merit_Account *account);",
    ):
        assert contract in reference_header
    for contract in (
        b"sizeof(merit_Account) == 16",
        b"offsetof(merit_Account, balance) == 8",
        b"int64_t merit_deposit(merit_Account * m0, int64_t m1);",
        b"int64_t merit_account_balance(const merit_Account * m0);",
    ):
        assert contract in header

    class Account(ctypes.Structure):
        _fields_ = [("id", ctypes.c_uint64), ("balance", ctypes.c_int64)]

    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    library = ctypes.CDLL(str(output.with_suffix(suffix)))
    library.merit_deposit.argtypes = [ctypes.POINTER(Account), ctypes.c_int64]
    library.merit_deposit.restype = ctypes.c_int64
    library.merit_account_balance.argtypes = [ctypes.POINTER(Account)]
    library.merit_account_balance.restype = ctypes.c_int64
    account = Account(1001, 100_000)
    assert library.merit_deposit(ctypes.byref(account), 12_550) == 112_550
    assert library.merit_account_balance(ctypes.byref(account)) == 112_550
    assert account.balance == 112_550

    consumer = tmp_path / "ledger-reference-consumer.c"
    consumer.write_text(
        '#include "reference-ledger.h"\n'
        'int main(void) {\n'
        '    merit_Account account = {1001, 100000};\n'
        '    if (merit_deposit(&account, 12550) != 112550) return 1;\n'
        '    if (merit_account_balance(&account) != 112550) return 2;\n'
        '    merit_LedgerResult result = merit_withdraw_checked(&account, 2525);\n'
        '    if (result.tag != merit_LedgerResult_Applied) return 3;\n'
        '    if (result.data.Applied != 110025) return 4;\n'
        '    return 0;\n'
        '}\n',
        encoding="utf-8", newline="\n",
    )
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    consumer_executable = tmp_path / ("ledger-reference-consumer.exe" if os.name == "nt" else "ledger-reference-consumer")
    compiled = subprocess.run(
        [compiler, "-std=c11", "-I", str(oracle_header.parent), str(consumer),
         str(output.with_suffix(suffix)), "-o", str(consumer_executable)],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    environment = os.environ.copy()
    library_path_key = "PATH" if os.name == "nt" else "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    environment[library_path_key] = str(tmp_path) + os.pathsep + environment.get(library_path_key, "")
    consumed = subprocess.run([str(consumer_executable)], capture_output=True, env=environment)
    assert consumed.returncode == 0, consumed.stderr


def test_sh3_v4_public_shared_build_preserves_cobol_finance_abi(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "cobol_finance_modernization"
    shutil.copytree(ROOT / "examples/projects/cobol_finance_modernization", root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    project = load_project(root / "Merit.toml")
    _, oracle_header, _ = build_shared(project, tmp_path / "reference-cobol")
    assert b"merit_TransferResult merit_apply_transfer" in oracle_header.read_bytes()

    # Both ordinary compilation and the all-public foreign-call path must
    # represent the same decimal, stable aggregate, and enum behavior.
    executable = tmp_path / "native-cobol-executable"
    assert project_cli_main([
        "build", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(executable),
    ]) == 0
    assert _result(executable.with_suffix(".exe" if os.name == "nt" else ""))[0] == 0

    output = tmp_path / "native-cobol-shared"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_bytes()
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    assert header == emit_c_header(module).encode("utf-8")

    consumer = tmp_path / "cobol-reference-consumer.c"
    consumer.write_text(
        '#include "reference-cobol.h"\n'
        'int main(void) {\n'
        '    merit_Account debit = merit_import_account((merit_CobolAccountRecord){1001001, 125000, 40});\n'
        '    merit_Account credit = merit_import_account((merit_CobolAccountRecord){2002002, 7525, 40});\n'
        '    merit_TransferPosting posting = merit_import_transfer(\n'
        '        (merit_CobolTransferRecord){1001001, 2002002, 12550, 41});\n'
        '    merit_TransferResult result = merit_apply_transfer(&debit, &credit, posting);\n'
        '    if (result.tag != merit_TransferResult_Committed) return 1;\n'
        '    if (result.data.Committed.debit_balance != 112450) return 2;\n'
        '    if (result.data.Committed.credit_balance != 20075) return 3;\n'
        '    if (result.data.Committed.sequence != 41) return 4;\n'
        '    merit_CobolAccountRecord exported = merit_export_account(&debit);\n'
        '    if (exported.balance != 112450 || exported.last_sequence != 41) return 5;\n'
        '    result = merit_apply_transfer(&debit, &credit, posting);\n'
        '    if (result.tag != merit_TransferResult_Rejected) return 6;\n'
        '    if (result.data.Rejected.tag != merit_TransferError_DuplicateOrOutOfOrder) return 7;\n'
        '    return 0;\n'
        '}\n',
        encoding="utf-8", newline="\n",
    )
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    consumer_executable = tmp_path / ("cobol-reference-consumer.exe" if os.name == "nt" else "cobol-reference-consumer")
    compiled = subprocess.run(
        [compiler, "-std=c11", "-I", str(oracle_header.parent), str(consumer),
         str(output.with_suffix(suffix)), "-o", str(consumer_executable)],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    environment = os.environ.copy()
    library_path_key = "PATH" if os.name == "nt" else "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    environment[library_path_key] = str(tmp_path) + os.pathsep + environment.get(library_path_key, "")
    consumed = subprocess.run([str(consumer_executable)], capture_output=True, env=environment)
    assert consumed.returncode == 0, consumed.stderr


@pytest.mark.parametrize("name", [
    "text_pipeline", "binary_packet", "generic_result", "trait_bounds",
    "generic_collections", "borrowed_views", "cobol_finance_modernization",
    "filesystem_capabilities", "ledger_app",
])
def test_sh3_v4_all_acceptance_public_shared_headers_match_mir_oracle(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver, name: str,
) -> None:
    root = tmp_path / name
    shutil.copytree(ROOT / "examples/projects" / name, root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    project = load_project(root / "Merit.toml")
    _, reference_header, _ = build_shared(project, tmp_path / "reference")
    assert reference_header.exists()

    output = tmp_path / "native-shared"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    assert output.with_suffix(".h").read_bytes() == emit_c_header(module).encode("utf-8")

def test_sh3_v4_public_owned_enum_with_resource_payload_fails_closed(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "resource_enum_abi"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="resource_enum_abi"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module resource_enum_abi\n'
        'pub stable("receipt-v1") struct Receipt { value:i64; other:i64; }\n'
        'pub enum Choice { HasBuffer(Buffer), Empty(Receipt) }\n'
        'pub fn choose(selector:i64)->Choice {\n'
        '    if (selector > 0) { return Empty(Receipt { value:1, other:3 }); }\n'
        '    else { return Empty(Receipt { value:2, other:4 }); }\n'
        '}\n'
        'fn main()->i32 { return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    executable = tmp_path / "resource_enum_executable"
    assert project_cli_main([
        "build", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(executable),
    ]) == 0
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    with pytest.raises(MirToCError, match="requires stable aggregate or Copy-enum payloads"):
        emit_c_header(module)

    shared = tmp_path / "resource_enum_shared"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(shared),
    ]) != 0
    assert not shared.with_suffix(".h").exists()


def test_sh3_v4_public_shared_vector_abi_matches_reference(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "vector_abi"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="vector_abi"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        'module vector_abi\n'
        'capability allocate;\n'
        'pub fn make_values(allocator:Allocator)->Vec<i64>\n'
        'requires_caps [allocate]\n'
        '{\n'
        '    var values:Vec<i64>=vec_new<i64>(allocator,2);\n'
        '    vec_push<i64>(values,4);\n'
        '    vec_push<i64>(values,5);\n'
        '    return values;\n'
        '}\n'
        'pub fn sum_values(borrow values:Vec<i64>)->i64 {\n'
        '    return checked_add(vec_get<i64>(values,0),vec_get<i64>(values,1));\n'
        '}\n'
        'pub fn consume_values(values:Vec<i64>)->i32 { drop(values); return 0; }\n'
        'fn main()->i32 { return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    project = load_project(root / "Merit.toml")
    _, reference_header, _ = build_shared(project, tmp_path / "reference-vector")
    assert b"merit_Vec__i64 merit_make_values" in reference_header.read_bytes()

    output = tmp_path / "native-vector"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    assert output.with_suffix(".h").read_bytes() == emit_c_header(module).encode("utf-8")

    consumer = tmp_path / "vector-reference-consumer.c"
    consumer.write_text(
        '#include "reference-vector.h"\n'
        'int main(void) {\n'
        '    merit_Allocator allocator = {0};\n'
        '    merit_Vec__i64 values = merit_make_values(allocator);\n'
        '    if (values.len != 2 || values.data[0] != 4 || values.data[1] != 5) return 1;\n'
        '    if (merit_sum_values(&values) != 9) return 2;\n'
        '    if (merit_consume_values(values) != 0) return 3;\n'
        '    return 0;\n'
        '}\n',
        encoding="utf-8", newline="\n",
    )
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    executable = tmp_path / ("vector-reference-consumer.exe" if os.name == "nt" else "vector-reference-consumer")
    compiled = subprocess.run(
        [compiler, "-std=c11", "-I", str(reference_header.parent), str(consumer),
         str(output.with_suffix(suffix)), "-o", str(executable)],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    environment = os.environ.copy()
    library_path_key = "PATH" if os.name == "nt" else "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    environment[library_path_key] = str(tmp_path) + os.pathsep + environment.get(library_path_key, "")
    consumed = subprocess.run([str(executable)], capture_output=True, env=environment)
    assert consumed.returncode == 0, consumed.stderr


def test_sh3_v4_compiler_all_public_shared_abi_matches_mir_oracle(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "compiler"
    shutil.copytree(
        ROOT / "examples/projects/bootstrap_lexer", root,
        ignore=shutil.ignore_patterns("build", ".merit"),
    )
    output = tmp_path / "native-compiler-shared"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    native_header = output.with_suffix(".h").read_bytes()
    assert native_header == emit_c_header(module).encode("utf-8")

    project = load_project(root / "Merit.toml")
    _, reference_header, _ = build_shared(
        project, tmp_path / "reference-compiler-shared",
    )
    public_structs = project.program.exports & project.program.structs.keys()
    assert {"CapabilityCatalogEntry", "ParseCursor", "ProjectRequestUnitSpan", "SfrNumericMagnitude"} <= public_structs
    for name in sorted(public_structs):
        assert f"}} merit_{name};".encode("utf-8") in native_header
    exported_functions = {
        function.name for function in project.program.functions
        if function.name in project.program.exports and function.name != "main"
    }
    native_functions = set(re.findall(
        r"\bmerit_([A-Za-z_][A-Za-z0-9_]*)\s*\(", native_header.decode("utf-8"),
    ))
    assert native_functions == exported_functions
    reference_functions = set(re.findall(
        r"\bmerit_([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        reference_header.read_text(encoding="utf-8"),
    ))
    assert exported_functions <= reference_functions
    consumer = tmp_path / "compiler-reference-consumer.c"
    consumer.write_text(
        '#include "reference-compiler-shared.h"\n'
        '#include <stdlib.h>\n'
        'int main(void) {\n'
        '    merit_HirExpressionRecord node = {0};\n'
        '    node.kind = 17; node.type_code = 2;\n'
        '    if (merit_hir_kind(&node) != 17) return 1;\n'
        '    merit_HirExpressionRecord changed = merit_hir_with_type(&node, 42);\n'
        '    if (changed.kind != 17 || changed.type_code != 42) return 2;\n'
        '    uint8_t bytes[] = "fn x(){}";\n'
        '    merit_Buffer source = {.data = bytes, .len = sizeof(bytes) - 1,\n'
        '                           .cap = sizeof(bytes) - 1, .allocator = {0}};\n'
        '    merit_Vec__Token tokens = merit_lex(&source, source.allocator);\n'
        '    if (tokens.len < 2 || tokens.data[0].kind != merit_token_identifier_kind()\n'
        '        || tokens.data[0].start != 0 || tokens.data[0].length != 2) return 3;\n'
        '    free(tokens.data);\n'
        '    return 0;\n'
        '}\n',
        encoding="utf-8", newline="\n",
    )
    compiler = shutil.which("cc") or shutil.which("gcc")
    assert compiler is not None
    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    executable = tmp_path / ("compiler-reference-consumer.exe" if os.name == "nt" else "compiler-reference-consumer")
    compiled = subprocess.run(
        [compiler, "-std=c11", "-I", str(reference_header.parent), str(consumer),
         str(output.with_suffix(suffix)), "-o", str(executable)],
        capture_output=True, text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    environment = os.environ.copy()
    library_path_key = "PATH" if os.name == "nt" else "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    environment[library_path_key] = str(tmp_path) + os.pathsep + environment.get(library_path_key, "")
    consumed = subprocess.run([str(executable)], capture_output=True, env=environment)
    assert consumed.returncode == 0, consumed.stderr


def test_sh3_v4_public_shared_builtin_resource_abi_matches_oracle(
    tmp_path: Path, native_v4_driver: NativeReplacementDriver,
) -> None:
    root = tmp_path / "resource_abi"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="resource_abi"\nentry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    (root / "src/main.mrt").write_text(
        "module resource_abi\n"
        "pub fn same_allocator(value:Allocator)->Allocator { return value; }\n"
        "pub fn slice_size(value:ByteSlice)->i64 { return slice_len(value); }\n"
        "pub fn buffer_size(borrow value:Buffer)->i64 { return buffer_len(value); }\n"
        "fn main()->i32 { return 0; }\n",
        encoding="utf-8", newline="\n",
    )
    output = tmp_path / "resource_abi"
    assert project_cli_main([
        "build-shared", str(root), "--compiler-path", str(native_v4_driver.executable),
        "-o", str(output),
    ]) == 0
    header = output.with_suffix(".h").read_bytes()
    manifest_path = root / ".merit" / REPLACEMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mir_path = manifest_path.parent / manifest["native_artifacts"]["canonical_mir"]["path"]
    module = parse_mir(json.loads(mir_path.read_bytes()))
    assert header == emit_c_header(module).encode("utf-8")
    assert b"merit_Allocator merit_same_allocator(merit_Allocator m0);" in header
    assert b"int64_t merit_slice_size(merit_ByteSlice m0);" in header
    assert b"int64_t merit_buffer_size(const merit_Buffer * m0);" in header

    class Allocator(ctypes.Structure):
        _fields_ = [("identity", ctypes.c_int32)]

    class ByteSlice(ctypes.Structure):
        _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("len", ctypes.c_size_t)]

    class Buffer(ctypes.Structure):
        _fields_ = [
            ("data", ctypes.POINTER(ctypes.c_uint8)),
            ("len", ctypes.c_size_t),
            ("capacity", ctypes.c_size_t),
            ("allocator", Allocator),
        ]

    suffix = ".dll" if os.name == "nt" else ".dylib" if sys.platform == "darwin" else ".so"
    library = ctypes.CDLL(str(output.with_suffix(suffix)))
    library.merit_same_allocator.argtypes = [Allocator]
    library.merit_same_allocator.restype = Allocator
    assert library.merit_same_allocator(Allocator(1)).identity == 1
    library.merit_slice_size.argtypes = [ByteSlice]
    library.merit_slice_size.restype = ctypes.c_int64
    data = (ctypes.c_uint8 * 3)(4, 5, 6)
    assert library.merit_slice_size(ByteSlice(data, 3)) == 3
    library.merit_buffer_size.argtypes = [ctypes.POINTER(Buffer)]
    library.merit_buffer_size.restype = ctypes.c_int64
    value = Buffer(data, 3, 3, Allocator(1))
    assert library.merit_buffer_size(ctypes.byref(value)) == 3
