import shutil
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CompileError
from merit.project.build import build, check, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
MANIFEST = PROJECT / "Merit.toml"
EXPECTED = "16\n1\n4\n36\n"


def test_bootstrap_lexer_matches_interpreter_native_and_ordered_c(tmp_path):
    project = load_project(MANIFEST)
    checker = check(project)
    assert interpret(project) == EXPECTED
    c_path, _, executable = build(project, tmp_path / "bootstrap_lexer")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == EXPECTED
    generated = c_path.read_text()
    assert "merit_Vec__Token _merit_result = {0};" in generated
    lexer_body = generated[generated.rindex("merit_Vec__Token merit_lex("):generated.index("int32_t main(")]
    assert lexer_body.index("merit_buffer_get(_merit_expr_") < lexer_body.index("merit_vec_push__Token(")
    operations = {(site["operation"], site["capability"]) for site in checker.hazardous_operations}
    assert ("vec_new__Token", "allocate") in operations
    assert ("vec_push__Token", "allocate") in operations


def test_bootstrap_lexer_reports_unterminated_string_token(tmp_path):
    project_root = tmp_path / "bootstrap_lexer"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    lexer_path = project_root / "src/lexer.mrt"
    source = lexer_path.read_text()
    original = 'let source: Buffer = buffer_from_string(allocator, "let total: i64 = 42;\\nprint(\\\"ok\\\", total + 1); // ok\\n");'
    replacement = 'let source: Buffer = buffer_from_string(allocator, "\\\"unterminated");'
    assert original in source
    lexer_path.write_text(source.replace(original, replacement))
    project = load_project(project_root / "Merit.toml")
    assert interpret(project) == "1\n5\n5\n13\n"
    _, _, executable = build(project, project_root / "bootstrap_lexer")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == "1\n5\n5\n13\n"


def test_bootstrap_lexer_allocation_is_compile_fail_without_capability_contract():
    project = load_project(MANIFEST)
    lexer = next(function for function in project.program.functions if function.name == "lex")
    lexer.requires_caps = []
    with pytest.raises(CompileError, match="vec_new__Token requires capabilities"):
        check(project)
