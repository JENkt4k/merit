import contextlib
import io
import json
import subprocess

import pytest

from merit.compiler import Checker, CompileError, Interpreter, compile_file, hir, mir, parse, type_needs_drop


IMPLICIT_DESTRUCTOR = '''module custom_destructor
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn main()->i32 { let marker:Marker=Marker{number:7}; return 0; }'''


def outputs(source: str, tmp_path) -> tuple[str, str]:
    program=parse(source);Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    source_path=tmp_path/'destructor.mrt';executable=tmp_path/'destructor'
    source_path.write_text(source);compile_file(source_path,executable)
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    return interpreted.getvalue(),native


def test_custom_destructor_runs_once_during_implicit_cleanup(tmp_path):
    program=parse(IMPLICIT_DESTRUCTOR);Checker(program).check()
    assert type_needs_drop('Marker',program)
    assert outputs(IMPLICIT_DESTRUCTOR,tmp_path) == ('7\n','7\n')


def test_custom_destructor_is_explicit_in_hir_and_mir():
    program=parse(IMPLICIT_DESTRUCTOR);Checker(program).check()
    hir_destructor=hir(program)['destructors'][0]
    mir_destructor=mir(program)['destructors'][0]
    assert hir_destructor['type'] == mir_destructor['type'] == 'Marker'
    assert hir_destructor['body'][0]['kind'] == 'print'
    assert mir_destructor['semantic_body'][0]['kind'] == 'print'
    json.dumps(hir_destructor);json.dumps(mir_destructor)


def test_explicit_drop_suppresses_implicit_custom_destructor(tmp_path):
    source=IMPLICIT_DESTRUCTOR.replace('return 0;','drop(marker); return 0;')
    assert outputs(source,tmp_path) == ('7\n','7\n')


def test_destructor_target_must_be_struct():
    source='''module bad_destructor
destructor Missing { print(1); }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5501: destructor target must be a struct'):
        Checker(parse(source)).check()


def test_destructor_rejects_ownership_changing_statements():
    source='''module bad_destructor_body
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { let value:i32=1; print(value); }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5502: destructor bodies currently allow only print and expression statements'):
        Checker(parse(source)).check()


def test_custom_destructor_runs_before_owned_field_cleanup(tmp_path):
    source='''module destructor_order
capability allocate;
struct Resource { data:Buffer; }
destructor Resource { print(buffer_len(self.data)); }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); let resource:Resource=Resource{data:buffer_from_string(allocator,"abc")}; drop(resource); } return 0; }'''
    assert outputs(source,tmp_path) == ('3\n','3\n')


def test_returned_owned_value_transfers_custom_destructor_obligation(tmp_path):
    source='''module destructor_move
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn make()->Marker { let marker:Marker=Marker{number:11}; return marker; }
fn main()->i32 { let marker:Marker=make(); drop(marker); return 0; }'''
    assert outputs(source,tmp_path) == ('11\n','11\n')


def test_recursive_aggregate_cleanup_invokes_nested_custom_destructor(tmp_path):
    source='''module nested_destructor
stable("marker-v1") struct Marker { number:i32; }
struct Wrapper { marker:Marker; }
destructor Marker { print(self.number); }
fn main()->i32 { let wrapper:Wrapper=Wrapper{marker:Marker{number:13}}; return 0; }'''
    assert outputs(source,tmp_path) == ('13\n','13\n')
