from pathlib import Path
import ctypes
import dataclasses
import json
import shutil
import subprocess

import pytest

from merit.compiler import CompileError
from merit.project.build import build, build_shared, check, interpret, shared_library_policy
from merit.project.cli import main as project_cli_main
from merit.project.loader import ProjectError, load_project

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "projects" / "ledger_app" / "Merit.toml"


@pytest.mark.parametrize(
    ('platform','expected'),
    [
        ('linux',('.so',('-shared',),True)),
        ('darwin',('.dylib',('-dynamiclib',),True)),
        ('win32',('.dll',('-shared',),False)),
    ],
)
def test_shared_library_policy_is_platform_specific(platform,expected):
    assert shared_library_policy(platform) == expected


def test_loads_and_checks_multimodule_project():
    project = load_project(EXAMPLE)
    assert len(project.units) == 5
    assert len(project.program.functions) == 7
    check(project)


def test_multimodule_interpreter_output(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = load_project(EXAMPLE)
    assert interpret(project) == "1100.25\n2\n10\n1001\n1100.25\n"


@pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler unavailable")
def test_multimodule_native_matches_interpreter(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = load_project(EXAMPLE)
    _, _, executable = build(project, tmp_path / "ledger")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True,cwd=tmp_path).stdout
    assert native == interpret(project)


@pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler unavailable")
def test_project_build_reuses_content_addressed_object(tmp_path):
    project = load_project(EXAMPLE)
    build(project, tmp_path / "first")
    objects = list((tmp_path / ".merit-cache").glob("*.o"))
    assert len(objects) == 1
    cached_object = objects[0]
    original_mtime = cached_object.stat().st_mtime_ns
    build(project, tmp_path / "second")
    assert list((tmp_path / ".merit-cache").glob("*.o")) == [cached_object]
    assert cached_object.stat().st_mtime_ns == original_mtime
    changed_manifest = dataclasses.replace(project.manifest, c_flags=("-O0",))
    build(dataclasses.replace(project, manifest=changed_manifest), tmp_path / "changed_flags")
    assert len(list((tmp_path / ".merit-cache").glob("*.o"))) == 2


@pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler unavailable")
def test_failed_object_compilation_does_not_publish_partial_cache_entry(tmp_path):
    project = load_project(EXAMPLE)
    invalid_manifest = dataclasses.replace(project.manifest, c_flags=("-fdefinitely-not-a-real-merit-test-flag",))
    with pytest.raises(subprocess.CalledProcessError):
        build(dataclasses.replace(project,manifest=invalid_manifest),tmp_path / "failed")
    cache = tmp_path / ".merit-cache"
    assert not list(cache.glob("*.o"))
    assert not list(cache.glob("*.tmp"))


@pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler unavailable")
def test_build_shared_exports_c_callable_merit_functions(tmp_path):
    project_root = tmp_path / "shared_api"
    (project_root / "src").mkdir(parents=True)
    (project_root / "Merit.toml").write_text(
        '[package]\nname = "shared_api"\nentry = "src/main.mrt"\nsources = ["src/*.mrt"]\n'
    )
    (project_root / "src" / "main.mrt").write_text(
        "module shared_api\n"
        "stable(\"secret-v1\") struct Secret { value:i32; }\n"
        "pub fn increment(value:i32)->i32 { return checked_add(value,1); }\n"
        "fn private_helper(value:i32)->i32 { return value; }\n"
        "fn main()->i32 { return 0; }\n"
    )
    project = load_project(project_root / "Merit.toml")
    _, header, library = build_shared(project, project_root / "build" / "libshared_api")
    assert library.suffix == shared_library_policy()[0]
    assert "int32_t merit_increment(int32_t value);" in header.read_text()
    assert "merit_private_helper" not in header.read_text()
    assert "merit_Secret" not in header.read_text()
    assert project.program.exports == {"increment"}
    shared = ctypes.CDLL(str(library))
    shared.merit_increment.argtypes = [ctypes.c_int32]
    shared.merit_increment.restype = ctypes.c_int32
    assert shared.merit_increment(41) == 42


def test_public_function_cannot_expose_private_project_type(tmp_path):
    project_root = tmp_path / "private_abi_leak"
    (project_root / "src").mkdir(parents=True)
    (project_root / "Merit.toml").write_text(
        '[package]\nname = "private_abi_leak"\nentry = "src/main.mrt"\nsources = ["src/*.mrt"]\n'
    )
    (project_root / "src" / "main.mrt").write_text(
        "module private_abi_leak\n"
        'stable("secret-v1") struct Secret { value:i32; }\n'
        "pub fn reveal(secret:Secret)->i32 { return secret.value; }\n"
        "fn main()->i32 { return 0; }\n"
    )
    with pytest.raises(ProjectError, match="public function reveal exposes private type Secret"):
        load_project(project_root / "Merit.toml")


@pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler unavailable")
def test_shared_library_stable_struct_abi_matches_foreign_caller(tmp_path):
    project_root = tmp_path / "shared_struct_api"
    (project_root / "src").mkdir(parents=True)
    (project_root / "Merit.toml").write_text(
        '[package]\nname = "shared_struct_api"\nentry = "src/main.mrt"\nsources = ["src/*.mrt"]\n'
    )
    (project_root / "src" / "main.mrt").write_text(
        "module shared_struct_api\n"
        'pub stable("point-v1") struct Point { x:i32; y:i32; }\n'
        "pub fn point_sum(point:Point)->i32 { return checked_add(point.x,point.y); }\n"
        "fn main()->i32 { return 0; }\n"
    )
    project = load_project(project_root / "Merit.toml")
    _, header, library = build_shared(project, project_root / "build" / "libshared_struct_api")
    generated_header = header.read_text()
    assert "Merit layout struct Point hash" in generated_header
    assert 'sizeof(merit_Point) == 8' in generated_header

    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]

    shared = ctypes.CDLL(str(library))
    shared.merit_point_sum.argtypes = [Point]
    shared.merit_point_sum.restype = ctypes.c_int32
    assert shared.merit_point_sum(Point(19, 23)) == 42


def test_missing_import_is_diagnostic(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "Merit.toml").write_text('[package]\nname="bad"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n')
    (tmp_path / "src" / "main.mrt").write_text('module bad\nimport absent;\nfn main() -> i32 { return 0; }\n')
    with pytest.raises(ProjectError, match="missing modules"):
        load_project(tmp_path / "Merit.toml")


def test_qualified_imported_function_resolves_and_preserves_parity(tmp_path):
    project_root = tmp_path / "qualified_import"
    (project_root / "src").mkdir(parents=True)
    (project_root / "Merit.toml").write_text(
        '[package]\nname = "qualified_import"\nentry = "src/main.mrt"\nsources = ["src/*.mrt"]\n'
    )
    (project_root / "src" / "domain.mrt").write_text(
        'module domain\npub stable("point-v1") struct Point { x:i32; }\n'
        "pub fn score(point:Point)->i32 { return point.x; }\n"
    )
    (project_root / "src" / "main.mrt").write_text(
        "module main\nimport domain;\nfn main()->i32 { let point:domain.Point=domain.Point{x:42}; print(domain.score(point)); return 0; }\n"
    )
    project = load_project(project_root / "Merit.toml")
    assert interpret(project) == "42\n"
    _,_,executable = build(project, project_root / "build" / "qualified_import")
    assert subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout == "42\n"


def test_qualified_name_requires_explicit_import(tmp_path, capsys):
    project_root = tmp_path / "unimported_qualified"
    (project_root / "src").mkdir(parents=True)
    (project_root / "Merit.toml").write_text(
        '[package]\nname = "unimported_qualified"\nentry = "src/main.mrt"\nsources = ["src/*.mrt"]\n'
    )
    (project_root / "src" / "domain.mrt").write_text(
        "module domain\npub fn answer()->i32 { return 42; }\n"
    )
    (project_root / "src" / "main.mrt").write_text(
        "module main\nfn main()->i32 { print(domain.answer()); return 0; }\n"
    )
    with pytest.raises(ProjectError,match="module main uses qualified name domain.answer without importing domain"):
        load_project(project_root / "Merit.toml")
    assert project_cli_main(["check",str(project_root),"--diagnostic-format","json"]) == 1
    payload=json.loads(capsys.readouterr().err)
    assert payload["code"] == "M8000"
    assert payload["path"] == str(project_root / "src" / "main.mrt")
    assert payload["line"] == 2


def test_cycle_is_rejected(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "Merit.toml").write_text('[package]\nname="cycle"\nentry="src/a.mrt"\nsources=["src/**/*.mrt"]\n')
    (tmp_path / "src" / "a.mrt").write_text('module a\nimport b;\nfn main() -> i32 { return 0; }\n')
    (tmp_path / "src" / "b.mrt").write_text('module b\nimport a;\nfn helper() -> i32 { return 0; }\n')
    with pytest.raises(ProjectError, match="import cycle"):
        load_project(tmp_path / "Merit.toml")


def test_project_layout_command_reports_generated_types(capsys):
    manifest = ROOT / "examples" / "projects" / "generic_collections" / "Merit.toml"
    assert project_cli_main(["layout", str(manifest)]) == 0
    out = capsys.readouterr().out
    layouts = {entry["name"]: entry for entry in json.loads(out)}
    assert layouts["Vec__Buffer"]["kind"] == "vector"
    assert len(layouts["Vec__Buffer"]["layout_hash"]) == 24
    assert layouts["Option__Vec__i64"]["kind"] == "enum"
    assert layouts["Result__Vec__i64__Error"]["payload_size"] == 32


def test_project_audit_command_reports_hazards(capsys):
    manifest = ROOT / "examples" / "projects" / "generic_collections" / "Merit.toml"
    assert project_cli_main(["audit", str(manifest)]) == 0
    audit = json.loads(capsys.readouterr().out)
    assert audit["declared_capabilities"] == ["allocate"]
    assert audit["sites"] == [{"function": "main", "capability": "allocate"}]
    requirements = {(entry["kind"], entry["operation"], entry["capability"], entry["hazard"]) for entry in audit["capability_requirements"]}
    assert ("builtin", "buffer_from_string", "allocate", "allocation") in requirements
    assert ("vector_intrinsic", "vec_new<T>", "allocate", "allocation") in requirements
    operations = {(entry["operation"], entry["capability"], entry["hazard"]) for entry in audit["hazardous_operations"]}
    assert ("buffer_from_string", "allocate", "allocation") in operations
    assert ("vec_new__Buffer", "allocate", "allocation") in operations


def test_filesystem_capability_project_verifies_in_temporary_directory(tmp_path, monkeypatch, capsys):
    manifest = ROOT / "examples" / "projects" / "filesystem_capabilities" / "Merit.toml"
    executable = tmp_path / "filesystem-capabilities"
    monkeypatch.chdir(tmp_path)

    assert project_cli_main(["verify", str(manifest), "-o", str(executable)]) == 0
    assert capsys.readouterr().out == "verified 1 modules; output matches (13 bytes)\n"
    assert (tmp_path / "merit-filesystem-capabilities.bin").read_bytes() == b"MRT"


def test_filesystem_capability_project_audit_classifies_read_and_write(capsys):
    manifest = ROOT / "examples" / "projects" / "filesystem_capabilities" / "Merit.toml"
    assert project_cli_main(["audit", str(manifest)]) == 0
    audit = json.loads(capsys.readouterr().out)

    assert audit["declared_capabilities"] == ["allocate", "file_read", "file_write"]
    operations = {
        (entry["operation"], entry["capability"], entry["hazard_class"], entry["review"], entry["scope"])
        for entry in audit["hazardous_operations"]
    }
    assert ("buffer_from_string", "allocate", "allocation", "memory-resource", "lexical") in operations
    assert ("file_read", "file_read", "filesystem_read", "io-read", "lexical") in operations
    assert ("file_write", "file_write", "filesystem_write", "io-write", "lexical") in operations


@pytest.mark.parametrize(
    ("capability", "block"),
    [
        ("file_read", "with capability file_read"),
        ("file_write", "with capability file_write"),
    ],
)
def test_filesystem_capability_project_rejects_unauthorized_io(tmp_path, capability, block):
    example = ROOT / "examples" / "projects" / "filesystem_capabilities"
    project_root = tmp_path / capability
    shutil.copytree(example, project_root)
    source = project_root / "src" / "main.mrt"
    source.write_text(source.read_text().replace(block, "with capability allocate"))

    with pytest.raises(CompileError, match=rf"requires capabilities \['{capability}'\]"):
        check(load_project(project_root / "Merit.toml"))
