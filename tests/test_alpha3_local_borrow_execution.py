"""Independent interpreter/native execution checks for RM1 local loans."""

import contextlib
import io
import subprocess

import pytest

from merit.compiler import Checker, Interpreter, compile_file, parse


def parity(source: str, tmp_path) -> tuple[str, str]:
    program=parse(source)
    Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(program).run()
    path=tmp_path/'local_borrow.mrt'
    executable=tmp_path/'local_borrow'
    path.write_text(source,encoding='utf-8')
    compile_file(path,executable)
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    return interpreted.getvalue(),native


@pytest.mark.parametrize(
    ("case", "body", "declarations", "functions", "expected"),
    [
        ("01", 'let x:String="a"; let r: borrow String = borrow x; print(r);', "", "", "a\n"),
        ("02", 'let x:String="a"; let r: borrow String = borrow x; let s: borrow String = borrow x; print(r); print(s);', "", "", "a\na\n"),
        ("04", 'var x:i32=1; let r: borrow i32 = borrow x; print(r); x=2; print(x);', "", "", "1\n2\n"),
        ("07", 'let x:Box=Box {value:1}; let r: borrow Box = borrow x; print(r.value); let y:Box=x; print(y.value);', 'struct Box { value:i32; }', "", "1\n1\n"),
        ("09", 'let x:String="a"; let r: borrow String = borrow x; print(r); drop(x);', "", "", "a\n"),
        ("18", 'var x:i32=1; with capability io { let r: borrow i32 = borrow x; print(r); } x=2; print(x);', 'capability io;', "", "1\n2\n"),
        ("24", 'let x:Box=Box {value:1}; let r: borrow Box = borrow x; inspect(r); print(r.value);', 'struct Box { value:i32; }', 'fn inspect(borrow value:Box)->i32 { return value.value; }', "1\n"),
    ],
)
def test_required_accepted_cases_have_interpreter_native_parity(case,body,declarations,functions,expected,tmp_path):
    source=f'module rm1\n{declarations}\n{functions}\nfn main()->i32 {{ {body} return 0; }}'
    assert parity(source,tmp_path)==(expected,expected)


def test_borrowed_parameter_origin_and_owner_destructor_are_identical(tmp_path):
    source=('module rm1\nstruct Box { value:i32; } destructor Box { print(9); }\n'
            'fn inspect(borrow x:Box)->i32 { let r: borrow Box = borrow x; return r.value; }\n'
            'fn main()->i32 { var x:Box=Box {value:1}; print(inspect(x)); '
            'let r: borrow Box = borrow x; print(r.value); replace(x,Box {value:2}); return 0; }')
    assert parity(source,tmp_path)==('1\n1\n9\n9\n','1\n1\n9\n9\n')


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ('return 0;', '1\n9\n'),
        ('drop(x); return 0;', '1\n9\n'),
        ('let y:Box=x; return 0;', '1\n9\n'),
        ('replace(x,Box {value:2}); return 0;', '1\n9\n9\n'),
    ],
)
def test_owner_cleanup_traces_after_final_use(tail,expected,tmp_path):
    source=('module rm1\nstruct Box { value:i32; } destructor Box { print(9); }\n'
            'fn main()->i32 { var x:Box=Box {value:1}; '
            'let r: borrow Box = borrow x; print(r.value); '+tail+' }')
    assert parity(source,tmp_path)==(expected,expected)


def test_early_return_preserves_owner_cleanup(tmp_path):
    source=('module rm1\nstruct Box { value:i32; } destructor Box { print(9); }\n'
            'fn work()->i32 { let x:Box=Box {value:1}; '
            'let r: borrow Box = borrow x; print(r.value); return 7; }\n'
            'fn main()->i32 { print(work()); return 0; }')
    assert parity(source,tmp_path)==('1\n9\n7\n','1\n9\n7\n')


def test_interpreter_reference_is_same_referent_object() -> None:
    source=('module rm1\nstruct Box { value:i32; }\n'
            'fn main()->i32 { let x:Box=Box {value:1}; '
            'let r: borrow Box = borrow x; return 0; }')
    program=parse(source);Checker(program).check()
    env={}
    Interpreter(program).block(program.functions[0].body[:2],env)
    owner,reference=program.functions[0].body[:2]
    assert env[owner.binding_id] is env[reference.binding_id]
