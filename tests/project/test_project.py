from pathlib import Path
import json
import shutil
import subprocess

import pytest

from merit.project.build import build, check, interpret
from merit.project.cli import main as project_cli_main
from merit.project.loader import ProjectError, load_project

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "projects" / "ledger_app" / "Merit.toml"


def test_loads_and_checks_multimodule_project():
    project = load_project(EXAMPLE)
    assert len(project.units) == 4
    assert len(project.program.functions) == 4
    check(project)


def test_multimodule_interpreter_output():
    project = load_project(EXAMPLE)
    assert interpret(project) == "1001\n1100.25\n"


@pytest.mark.skipif(shutil.which("cc") is None, reason="C compiler unavailable")
def test_multimodule_native_matches_interpreter(tmp_path):
    project = load_project(EXAMPLE)
    _, _, executable = build(project, tmp_path / "ledger")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpret(project)


def test_missing_import_is_diagnostic(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "Merit.toml").write_text('[package]\nname="bad"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n')
    (tmp_path / "src" / "main.mrt").write_text('module bad\nimport absent;\nfn main() -> i32 { return 0; }\n')
    with pytest.raises(ProjectError, match="missing modules"):
        load_project(tmp_path / "Merit.toml")


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
    assert layouts["Result__Vec__i64__Error"]["payload_size"] == 24


def test_project_audit_command_reports_hazards(capsys):
    manifest = ROOT / "examples" / "projects" / "generic_collections" / "Merit.toml"
    assert project_cli_main(["audit", str(manifest)]) == 0
    audit = json.loads(capsys.readouterr().out)
    assert audit["declared_capabilities"] == ["allocate"]
    assert audit["sites"] == [{"function": "main", "capability": "allocate"}]
    operations = {(entry["operation"], entry["capability"], entry["hazard"]) for entry in audit["hazardous_operations"]}
    assert ("buffer_from_string", "allocate", "allocation") in operations
    assert ("vec_new__Buffer", "allocate", "allocation") in operations
