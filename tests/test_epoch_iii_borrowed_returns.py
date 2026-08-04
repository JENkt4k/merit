import contextlib
import ctypes
import io
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, compile_file, hir, mir, parse
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


def test_validated_borrowed_return_can_relay_shared_origin(tmp_path):
    source_text='''module relayed_shared_borrow
stable("v1") struct Value { number:i32; }
fn expose(borrow value:Value)->borrow Value { return value; }
fn relay(borrow value:Value)->borrow Value { return expose(value); }
fn main()->i32 { let value:Value=Value{number:41}; print(relay(value).number); return 0; }'''
    assert parity(source_text,tmp_path) == ('41\n','41\n')


def test_relayed_borrow_origin_is_explicit_in_hir_and_mir():
    source_text='''module relayed_borrow_ir
stable("v1") struct Value { number:i32; }
fn expose(borrow input:Value)->borrow Value { return input; }
fn relay(borrow value:Value)->borrow Value { return expose(value); }
fn main()->i32 { return 0; }'''
    program=parse(source_text);Checker(program).check()
    assert hir(program)['functions'][1]['borrowed_origin'] == 'value'
    lowered=mir(program)['functions'][1]
    assert lowered['return_mode'] == 'borrow'
    assert lowered['borrowed_origin'] == 'value'


def test_validated_borrowed_return_can_relay_mutable_origin(tmp_path):
    source_text='''module relayed_mutable_borrow
stable("v1") struct Value { number:i32; }
fn expose_mut(borrow_mut value:Value)->borrow_mut Value { return value; }
fn relay_mut(borrow_mut value:Value)->borrow_mut Value { return expose_mut(value); }
fn main()->i32 { var value:Value=Value{number:1}; relay_mut(value).number=43; print(value.number); return 0; }'''
    assert parity(source_text,tmp_path) == ('43\n','43\n')


def test_mutable_relay_rejects_shared_intermediate():
    source_text='''module invalid_mutable_relay
stable("v1") struct Value { number:i32; }
fn expose(borrow value:Value)->borrow Value { return value; }
fn relay_mut(borrow_mut value:Value)->borrow_mut Value { return expose(value); }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5308: borrow_mut return cannot relay shared borrowed result from value'):
        Checker(parse(source_text)).check()


def test_relayed_borrow_requires_one_consistent_caller_origin():
    source_text='''module inconsistent_relayed_borrow
stable("v1") struct Value { number:i32; }
fn expose(borrow value:Value)->borrow Value { return value; }
fn choose(borrow left:Value,borrow right:Value)->borrow Value { if left.number { return expose(left); } else { return expose(right); } }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5305: borrowed return must have one consistent parameter origin'):
        Checker(parse(source_text)).check()


def test_cyclic_borrowed_relays_cannot_establish_an_origin():
    source_text='''module cyclic_borrowed_relay
stable("v1") struct Value { number:i32; }
fn first(borrow value:Value)->borrow Value { return second(value); }
fn second(borrow value:Value)->borrow Value { return first(value); }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5300: borrowed return must originate from a borrowed parameter'):
        Checker(parse(source_text)).check()


def test_caller_cannot_move_origin_while_relayed_borrow_argument_is_live():
    source_text='''module borrowed_origin_move_conflict
stable("v1") struct Value { number:i32; }
fn expose(borrow value:Value)->borrow Value { return value; }
fn observe_and_consume(borrow view:Value,owned:Value)->i32 { return view.number+owned.number; }
fn main()->i32 { let value:Value=Value{number:1}; return observe_and_consume(expose(value),value); }'''
    with pytest.raises(CompileError,match='M5307: cannot move value while its borrowed result is live for call to observe_and_consume'):
        Checker(parse(source_text)).check()


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


def test_assignment_evaluates_value_before_side_effecting_borrowed_target(tmp_path):
    source_text='''module mutable_borrowed_assignment_order
stable("v1") struct Value { number:i32; calls:i32; }
fn expose_mut(borrow_mut value:Value)->borrow_mut Value { value.calls=value.calls+1; return value; }
fn replacement(borrow_mut value:Value)->i32 { value.calls=value.calls+10; return value.calls; }
fn main()->i32 { var value:Value=Value{number:1,calls:0}; expose_mut(value).number=replacement(value); print(value.calls); print(value.number); return 0; }'''
    assert parity(source_text,tmp_path) == ('11\n10\n','11\n10\n')
    program=parse(source_text);Checker(program).check();c_source=CGenerator(program).generate()
    assert c_source.index('_merit_assign_value_') < c_source.index('_merit_assign_address_')


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
    for name in ('merit_view_record','merit_edit_record','merit_view_record_relay','merit_edit_record_relay'):
        function=getattr(library,name)
        function.argtypes=[ctypes.POINTER(Record)]
        function.restype=ctypes.POINTER(Record)
    record=Record(31)
    assert library.merit_view_record(ctypes.byref(record)).contents.number == 31
    assert library.merit_view_record_relay(ctypes.byref(record)).contents.number == 31
    library.merit_edit_record(ctypes.byref(record)).contents.number=37
    assert record.number == 37
    library.merit_edit_record_relay(ctypes.byref(record)).contents.number=41
    assert record.number == 41


def test_generated_c_signatures_preserve_borrow_constness():
    shared=parse(source('borrow value: Value','return value;'))
    mutable=parse(source('borrow_mut value: Value','return value;').replace('-> borrow Value','-> borrow_mut Value'))
    assert 'const merit_Value * merit_expose(const merit_Value *value);' in CGenerator(shared).header()
    assert 'merit_Value * merit_expose(merit_Value *value);' in CGenerator(mutable).header()


def test_borrowed_return_postcondition_uses_pointer_result(tmp_path):
    source_text='''module borrowed_return_contract
stable("v1") struct Value { number:i32; }
fn expose(borrow value:Value)->borrow Value ensures result.number == value.number; { return value; }
fn main()->i32 { let value:Value=Value{number:67}; print(expose(value).number); return 0; }'''
    assert parity(source_text,tmp_path) == ('67\n','67\n')


def test_borrowed_return_assignment_evaluates_target_call_once(tmp_path):
    source_text='''module borrowed_target_once
stable("v1") struct Value { number:i32; }
fn expose_mut(borrow_mut value:Value)->borrow_mut Value { print(1); return value; }
fn main()->i32 { var value:Value=Value{number:0}; expose_mut(value).number=71; print(value.number); return 0; }'''
    assert parity(source_text,tmp_path) == ('1\n71\n','1\n71\n')


def test_borrowed_return_replacement_evaluates_target_call_once(tmp_path):
    source_text='''module borrowed_replace_once
capability allocate;
struct Resource { data:Buffer; }
fn expose_mut(borrow_mut value:Resource)->borrow_mut Resource { print(1); return value; }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var resource:Resource=Resource{data:buffer_from_string(allocator,"old")}; let replacement:Buffer=buffer_from_string(allocator,"replacement"); replace(expose_mut(resource).data,replacement); print(buffer_len(resource.data)); } return 0; }'''
    assert parity(source_text,tmp_path) == ('1\n11\n','1\n11\n')
