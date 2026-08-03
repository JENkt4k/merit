import contextlib
import ctypes
import io
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, compile_file, hir, parse
from merit.project.build import build, build_shared, check, interpret
from merit.project.loader import load_project


def source(signature: str, body: str) -> str:
    return f'''module borrowed_returns
stable("v1") struct Value {{ number: i32; }}
fn expose({signature}) -> borrow Value {{ {body} }}
fn main() -> i32 {{ return 0; }}'''


def test_borrowed_return_syntax_is_explicit_in_hir():
    program = parse(source("borrow value: Value", "return value;"))
    function = hir(program)["functions"][0]
    assert function["return"] == "Value"
    assert function["return_mode"] == "borrow"


def test_borrowed_return_requires_borrowed_parameter_origin():
    program = parse(source("value: Value", "return value;"))
    with pytest.raises(CompileError, match="M5300: borrowed return must originate from a borrowed parameter"):
        Checker(program).check()


def test_mutable_borrowed_return_requires_mutable_borrow_parameter():
    program = parse(source("borrow value: Value", "return value;").replace("-> borrow Value", "-> borrow_mut Value"))
    with pytest.raises(CompileError, match="M5301: borrow_mut return requires borrow_mut parameter value"):
        Checker(program).check()


def test_valid_borrow_origin_is_accepted():
    program = parse(source("borrow value: Value", "return value;"))
    Checker(program).check()


def parity(source_text, tmp_path):
    program=parse(source_text);Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    source_path=tmp_path/'borrowed_return.mrt';executable=tmp_path/'borrowed_return'
    source_path.write_text(source_text);compile_file(source_path,executable)
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    return interpreted.getvalue(),native


def test_borrowed_return_supports_ephemeral_field_access(tmp_path):
    source_text=source('borrow value: Value','return value;').replace(
        'fn main() -> i32 { return 0; }',
        'fn main() -> i32 { let value:Value=Value{number:17}; print(expose(value).number); return 0; }',
    )
    assert parity(source_text,tmp_path) == ('17\n','17\n')


def test_mutable_borrowed_return_propagates_caller_origin(tmp_path):
    source_text='''module mutable_borrowed_return
stable("v1") struct Value { number:i32; }
fn expose_mut(borrow_mut value:Value)->borrow_mut Value { return value; }
fn update(borrow_mut value:Value)->i32 { value.number=23; return value.number; }
fn main()->i32 { var value:Value=Value{number:1}; print(update(expose_mut(value))); print(value.number); return 0; }'''
    assert parity(source_text,tmp_path) == ('23\n23\n','23\n23\n')


def test_borrowed_return_cannot_be_stored_as_owned_value():
    source_text=source('borrow value: Value','return value;').replace(
        'fn main() -> i32 { return 0; }',
        'fn main() -> i32 { let value:Value=Value{number:1}; let alias:Value=expose(value); return 0; }',
    )
    with pytest.raises(CompileError,match='M5304: borrowed return cannot be stored in an owned binding'):
        Checker(parse(source_text)).check()


def test_borrowed_return_cannot_be_passed_by_value():
    source_text=source('borrow value: Value','return value;').replace(
        'fn main() -> i32 { return 0; }',
        'fn consume(value:Value)->i32 { return value.number; }\nfn main() -> i32 { let value:Value=Value{number:1}; return consume(expose(value)); }',
    )
    with pytest.raises(CompileError,match='M5304: borrowed return cannot be passed by value'):
        Checker(parse(source_text)).check()


def test_shared_borrowed_return_cannot_escalate_to_mutable():
    source_text=source('borrow value: Value','return value;').replace(
        'fn main() -> i32 { return 0; }',
        'fn update(borrow_mut value:Value)->i32 { value.number=2; return value.number; }\nfn main() -> i32 { var value:Value=Value{number:1}; return update(expose(value)); }',
    )
    with pytest.raises(CompileError,match='M5306: shared borrowed return cannot satisfy borrow_mut'):
        Checker(parse(source_text)).check()


def test_borrowed_return_requires_one_consistent_origin():
    source_text='''module inconsistent_borrowed_return
stable("v1") struct Value { number:i32; }
fn choose(borrow left:Value,borrow right:Value)->borrow Value { if left.number { return left; } else { return right; } }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5305: borrowed return must have one consistent parameter origin'):
        Checker(parse(source_text)).check()


def test_mutable_borrowed_return_supports_direct_field_assignment(tmp_path):
    source_text='''module mutable_borrowed_lvalue
stable("v1") struct Value { number:i32; }
fn expose_mut(borrow_mut value:Value)->borrow_mut Value { return value; }
fn main()->i32 { var value:Value=Value{number:1}; expose_mut(value).number=29; print(value.number); return 0; }'''
    assert parity(source_text,tmp_path) == ('29\n','29\n')


def test_shared_borrowed_return_rejects_direct_field_assignment():
    source_text=source('borrow value: Value','return value;').replace(
        'fn main() -> i32 { return 0; }',
        'fn main() -> i32 { var value:Value=Value{number:1}; expose(value).number=2; return 0; }',
    )
    with pytest.raises(CompileError,match='M5306: shared borrowed return cannot be mutated'):
        Checker(parse(source_text)).check()


def test_mutable_borrowed_return_supports_owned_field_replacement(tmp_path):
    source_text='''module mutable_borrowed_replace
capability allocate;
struct Resource { data:Buffer; }
fn expose_mut(borrow_mut value:Resource)->borrow_mut Resource { return value; }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var resource:Resource=Resource{data:buffer_from_string(allocator,"old")}; let replacement:Buffer=buffer_from_string(allocator,"new-value"); replace(expose_mut(resource).data,replacement); print(buffer_len(resource.data)); } return 0; }'''
    assert parity(source_text,tmp_path) == ('9\n','9\n')


def test_borrowed_views_project_preserves_interpreter_native_parity(tmp_path):
    project=load_project(Path('examples/projects/borrowed_views/Merit.toml'))
    check(project)
    assert interpret(project) == '5\n8\n'
    _,_,executable=build(project,tmp_path/'borrowed_views')
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    assert native == '5\n8\n'


def test_borrowed_views_are_stable_shared_library_pointers(tmp_path):
    project=load_project(Path('examples/projects/borrowed_views/Merit.toml'))
    _,_,library_path=build_shared(project,tmp_path/'libborrowed_views')
    class Record(ctypes.Structure):
        _fields_=[('number',ctypes.c_int32)]
    library=ctypes.CDLL(str(library_path))
    for name in ('merit_view_record','merit_edit_record'):
        function=getattr(library,name)
        function.argtypes=[ctypes.POINTER(Record)]
        function.restype=ctypes.POINTER(Record)
    record=Record(31)
    assert library.merit_view_record(ctypes.byref(record)).contents.number == 31
    library.merit_edit_record(ctypes.byref(record)).contents.number=37
    assert record.number == 37


def test_generated_c_signatures_preserve_borrow_constness():
    shared=parse(source('borrow value: Value','return value;'))
    mutable=parse(source('borrow_mut value: Value','return value;').replace('-> borrow Value','-> borrow_mut Value'))
    assert 'const merit_Value * merit_expose(const merit_Value *value);' in CGenerator(shared).header()
    assert 'merit_Value * merit_expose(merit_Value *value);' in CGenerator(mutable).header()
