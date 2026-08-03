import contextlib
import io
from pathlib import Path
import subprocess

import pytest

from merit.compiler import Checker, CompileError, Interpreter, parse
from merit.project.build import build, interpret
from merit.project.loader import ProjectError, load_project

ROOT = Path(__file__).resolve().parents[1]
RESULT_APP = ROOT / "examples" / "projects" / "result_app" / "Merit.toml"


def checked(source: str):
    program = parse(source)
    Checker(program).check()
    return program


def test_payload_enum_and_exhaustive_match_interpret():
    source = '''module x
enum Maybe { Some(i32), None }
fn main()->i32 { let x:Maybe=Some(7); match (x) { Some(v)=>{print(v);} None=>{print(0);} } return 0; }
'''
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        Interpreter(checked(source)).run()
    assert output.getvalue() == "7\n"


def test_non_exhaustive_match_is_rejected():
    source = '''module x
enum Maybe { Some(i32), None }
fn main()->i32 { let x:Maybe=None(); match (x) { None=>{print(0);} } return 0; }
'''
    with pytest.raises(CompileError, match="non-exhaustive"):
        checked(source)


def test_payload_binding_is_required():
    source = '''module x
enum Maybe { Some(i32), None }
fn main()->i32 { let x:Maybe=Some(1); match (x) { Some=>{print(1);} None=>{print(0);} } return 0; }
'''
    with pytest.raises(CompileError, match="requires payload binding"):
        checked(source)


def test_try_propagates_typed_error():
    source = '''module x
enum E { Bad }
enum R { Ok(i32), Err(E) }
fn value(x:i32)->R { if x < 0 { return Err(Bad()); } else { return Ok(x); } }
fn twice(x:i32)->R { let a:i32=try value(x); return Ok(checked_add(a,a)); }
fn main()->i32 { let r:R=twice(-1); match (r) { Ok(v)=>{print(v);} Err(e)=>{print(9);} } return 0; }
'''
    output = io.StringIO()
    with contextlib.redirect_stdout(output): Interpreter(checked(source)).run()
    assert output.getvalue() == "9\n"


def test_result_project_interpreter_and_native_match(tmp_path):
    project = load_project(RESULT_APP)
    assert interpret(project) == "42\n10\n20\n"
    _, _, executable = build(project, tmp_path / "result_app")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpret(project)


def test_private_cross_module_symbol_is_rejected(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "Merit.toml").write_text('[package]\nname="private"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n')
    (tmp_path / "src" / "library.mrt").write_text('module library\nfn hidden()->i32{return 1;}\n')
    (tmp_path / "src" / "main.mrt").write_text('module main\nimport library;\nfn main()->i32{return hidden();}\n')
    with pytest.raises(ProjectError, match="private symbol hidden"):
        load_project(tmp_path / "Merit.toml")


def test_public_cross_module_symbol_is_allowed(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "Merit.toml").write_text('[package]\nname="public"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n')
    (tmp_path / "src" / "library.mrt").write_text('module library\npub fn visible()->i32{return 1;}\n')
    (tmp_path / "src" / "main.mrt").write_text('module main\nimport library;\nfn main()->i32{return visible();}\n')
    load_project(tmp_path / "Merit.toml")
