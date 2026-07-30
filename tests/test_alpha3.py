from pathlib import Path
import subprocess
import pytest
from merit.compiler import parse, Checker, CompileError, Interpreter, CGenerator, mir, compile_file


def checked(src: str):
    p=parse(src); Checker(p).check(); return p


def test_conflicting_mutable_and_shared_loans_rejected():
    src='''module x
stable("v1") struct S { x:i32; }
fn collide(borrow_mut a:S, borrow b:S)->i32 { return a.x; }
fn main()->i32 { var s:S=S{x:1}; return collide(s,s); }'''
    with pytest.raises(CompileError, match='conflicting loans'):
        Checker(parse(src)).check()


def test_mutable_borrow_requires_mutable_binding():
    src='''module x
stable("v1") struct S { x:i32; }
fn alter(borrow_mut a:S)->i32 { a.x=2; return a.x; }
fn main()->i32 { let s:S=S{x:1}; return alter(s); }'''
    with pytest.raises(CompileError, match='not mutable'):
        Checker(parse(src)).check()


def test_use_after_explicit_drop_rejected():
    src='''module x
stable("v1") struct S { x:i32; }
fn main()->i32 { let s:S=S{x:1}; drop(s); return s.x; }'''
    with pytest.raises(CompileError, match='dropped value'):
        Checker(parse(src)).check()


def test_drop_of_borrowed_parameter_rejected():
    src='''module x
stable("v1") struct S { x:i32; }
fn bad(borrow s:S)->i32 { drop(s); return 0; }
fn main()->i32 { let s:S=S{x:1}; return bad(s); }'''
    with pytest.raises(CompileError, match='cannot drop borrowed'):
        Checker(parse(src)).check()


def test_mir_inserts_reverse_implicit_drops():
    src='''module x
stable("v1") struct S { x:i32; }
fn main()->i32 { let a:S=S{x:1}; let b:S=S{x:2}; return 0; }'''
    p=checked(src)
    statements=mir(p)['functions'][0]['blocks'][0]['statements']
    assert statements[-2:]==[('drop_implicit','b'),('drop_implicit','a')]


def test_c_backend_uses_pointers_for_borrows():
    src='''module x
stable("v1") struct S { x:i32; }
fn alter(borrow_mut s:S)->i32 { s.x=2; return s.x; }
fn main()->i32 { var s:S=S{x:1}; return alter(s); }'''
    c=CGenerator(checked(src)).generate()
    assert 'merit_alter(merit_S *s)' in c
    assert 's->x = 2;' in c
    assert 'merit_alter(&s)' in c


def test_postcondition_result_and_old_interpreter():
    src='''module x
fn inc(x:i32)->i32 ensures result == old(x) + 1; { return x + 1; }
fn main()->i32 { return inc(4); }'''
    p=checked(src)
    assert Interpreter(p).run().value==5


def test_native_and_interpreter_match_for_borrowed_mutation(tmp_path):
    src='''module x
stable("v1") struct S { x:i32; }
fn alter(borrow_mut s:S)->i32 { s.x=7; return s.x; }
fn main()->i32 { var s:S=S{x:1}; print(alter(s)); print(s.x); return 0; }'''
    path=tmp_path/'x.mrt'; path.write_text(src)
    p=checked(src)
    exe=tmp_path/'x'
    compile_file(path,exe)
    native=subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout
    assert native=='7\n7\n'
