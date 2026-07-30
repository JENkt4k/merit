import contextlib, io, subprocess, tempfile
from pathlib import Path
import pytest
from merit.compiler import parse, Checker, Interpreter, CGenerator, compile_file, CompileError

ROOT=Path(__file__).parents[1]

def program(text):
    p=parse(text); Checker(p).check(); return p

def test_control_flow_interpreter_and_native_match():
    path=ROOT/'examples'/'control_flow.mrt'
    p=program(path.read_text())
    out=io.StringIO()
    with contextlib.redirect_stdout(out): Interpreter(p).run()
    assert out.getvalue()=='115.76\n1\n3.33\n'
    with tempfile.TemporaryDirectory() as td:
        exe=Path(td)/'p';compile_file(path,exe)
        native=subprocess.run([str(exe)],capture_output=True,text=True,check=True).stdout
    assert native==out.getvalue()

def test_native_postcondition_and_old_are_emitted():
    p=program((ROOT/'examples'/'borrowed_component.mrt').read_text())
    c=CGenerator(p).generate()
    assert '_merit_old_0' in c
    assert 'postcondition failed in deposit' in c
    assert '_merit_result' in c

def test_stable_struct_gets_static_asserts():
    p=program((ROOT/'examples'/'account_component.mrt').read_text())
    h=CGenerator(p).header()
    assert '_Static_assert(sizeof(merit_Account) == 16' in h
    assert '__builtin_offsetof(merit_Account, balance) == 8' in h

def test_branch_consumption_is_conservative():
    src='''module x
stable("v1") struct S { x: i32; }
fn take(s: S) -> i32 { return s.x; }
fn main() -> i32 { let a: S = S { x: 1 }; if (1 == 1) { take(a); } else { print(0); } print(a.x); return 0; }
'''
    with pytest.raises(CompileError, match='moved'):
        program(src)

def test_loop_mutation_requires_var():
    src='''module x
fn main() -> i32 { let i: i32 = 0; while (i < 2) { i = checked_add(i, 1); } return i; }
'''
    with pytest.raises(CompileError, match='immutable'):
        program(src)
