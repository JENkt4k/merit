import contextlib
import io
import json
import subprocess

import pytest

from merit.compiler import Checker, CompileError, Interpreter, compile_file, hir, mir, parse, type_needs_drop
from merit.project.build import build, check, interpret
from merit.project.loader import ProjectError, load_project


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
    with pytest.raises(CompileError,match='M5502: destructor body statement may change ownership or capabilities'):
        Checker(parse(source)).check()


def test_destructor_supports_copy_field_mutation_and_control_flow(tmp_path):
    source='''module structured_destructor
stable("counter-v1") struct Counter { number:i32; }
destructor Counter { if self.number { self.number=checked_add(self.number,1); } else { self.number=10; } while self.number < 3 { self.number=checked_add(self.number,1); } print(self.number); }
fn main()->i32 { let first:Counter=Counter{number:1}; let second:Counter=Counter{number:0}; return 0; }'''
    assert outputs(source,tmp_path) == ('10\n3\n','10\n3\n')


def test_destructor_still_rejects_owned_field_assignment():
    source='''module unsafe_destructor_assignment
struct Resource { data:Buffer; }
destructor Resource { self.data=self.data; }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M5201: cannot assign into owned storage self.data'):
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


def test_owned_value_parameter_receives_implicit_cleanup(tmp_path):
    source='''module destructor_parameter
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn consume(marker:Marker)->i32 { return marker.number; }
fn main()->i32 { let marker:Marker=Marker{number:17}; return consume(marker)-17; }'''
    assert outputs(source,tmp_path) == ('17\n','17\n')


def test_returned_owned_parameter_transfers_cleanup_obligation(tmp_path):
    source='''module destructor_parameter_return
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn relay(marker:Marker)->Marker { return marker; }
fn main()->i32 { let marker:Marker=Marker{number:19}; let result:Marker=relay(marker); drop(result); return 0; }'''
    assert outputs(source,tmp_path) == ('19\n','19\n')


def test_discarded_owned_temporary_is_rejected():
    source='''module discarded_owned_temporary
struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn make()->Marker { return Marker{number:23}; }
fn main()->i32 { make(); return 0; }'''
    with pytest.raises(CompileError,match='M5210: owned temporary Marker must be bound, transferred, or explicitly dropped'):
        Checker(parse(source)).check()


def test_owned_temporary_can_transfer_directly_to_value_parameter(tmp_path):
    source='''module transferred_owned_temporary
struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn make()->Marker { return Marker{number:29}; }
fn consume(marker:Marker)->i32 { return marker.number; }
fn main()->i32 { return consume(make())-29; }'''
    assert outputs(source,tmp_path) == ('29\n','29\n')


def test_owned_match_payload_must_be_consumed_in_its_arm():
    source='''module unconsumed_match_payload
struct Marker { number:i32; }
destructor Marker { print(self.number); }
enum MaybeMarker { SomeMarker(Marker), NoMarker }
fn main()->i32 { let marker:Marker=Marker{number:31}; let maybe:MaybeMarker=SomeMarker(marker); match (maybe) { SomeMarker(value)=>{ print(value.number); } NoMarker=>{} } return 0; }'''
    with pytest.raises(CompileError,match='M5211: owned match payload value must be moved or dropped in arm SomeMarker'):
        Checker(parse(source)).check()


def test_owned_match_payload_can_transfer_through_return(tmp_path):
    source='''module returned_match_payload
struct Marker { number:i32; }
destructor Marker { print(self.number); }
enum MaybeMarker { SomeMarker(Marker), NoMarker }
fn unwrap(maybe:MaybeMarker)->Marker { match (maybe) { SomeMarker(value)=>{ return value; } NoMarker=>{ return Marker{number:0}; } } }
fn main()->i32 { let marker:Marker=Marker{number:37}; let maybe:MaybeMarker=SomeMarker(marker); let result:Marker=unwrap(maybe); drop(result); return 0; }'''
    assert outputs(source,tmp_path) == ('37\n','37\n')


def test_c_composite_definitions_follow_by_value_dependencies(tmp_path):
    source='''module composite_definition_order
enum State { Ready }
struct Holder { state:State; }
fn main()->i32 { let holder:Holder=Holder{state:Ready()}; match (holder.state) { Ready=>{} } return 0; }'''
    assert outputs(source,tmp_path) == ('','')


def test_recursive_aggregate_cleanup_invokes_nested_custom_destructor(tmp_path):
    source='''module nested_destructor
stable("marker-v1") struct Marker { number:i32; }
struct Wrapper { marker:Marker; }
destructor Marker { print(self.number); }
fn main()->i32 { let wrapper:Wrapper=Wrapper{marker:Marker{number:13}}; return 0; }'''
    assert outputs(source,tmp_path) == ('13\n','13\n')


def write_project(tmp_path, library: str, main: str):
    (tmp_path/'src').mkdir()
    (tmp_path/'Merit.toml').write_text('[package]\nname="destructor_project"\nentry="src/main.mrt"\nsources=["src/*.mrt"]\n')
    (tmp_path/'src'/'library.mrt').write_text(library)
    (tmp_path/'src'/'main.mrt').write_text(main)
    return tmp_path/'Merit.toml'


def test_project_destructor_can_call_imported_public_function(tmp_path):
    manifest=write_project(
        tmp_path,
        'module library\npub fn increment(value:i32)->i32 { return checked_add(value,1); }\n',
        'module main\nimport library;\nstable("marker-v1") struct Marker { number:i32; }\ndestructor Marker { print(increment(self.number)); }\nfn main()->i32 { let marker:Marker=Marker{number:20}; return 0; }\n',
    )
    project=load_project(manifest)
    assert interpret(project) == '21\n'
    _,_,executable=build(project,tmp_path/'build'/'destructor_project')
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    assert native == '21\n'


def test_project_destructor_rejects_private_imported_function(tmp_path):
    manifest=write_project(
        tmp_path,
        'module library\nfn hidden(value:i32)->i32 { return value; }\n',
        'module main\nimport library;\nstable("marker-v1") struct Marker { number:i32; }\ndestructor Marker { print(hidden(self.number)); }\nfn main()->i32 { let marker:Marker=Marker{number:1}; return 0; }\n',
    )
    with pytest.raises(ProjectError,match='private symbol hidden'):
        load_project(manifest)


def test_project_destructor_diagnostic_maps_to_its_source_file(tmp_path):
    manifest=write_project(
        tmp_path,
        'module library\npub fn visible(value:i32)->i32 { return value; }\n',
        'module main\nimport library;\nstable("marker-v1") struct Marker { number:i32; }\ndestructor Marker { let invalid:i32=1; }\nfn main()->i32 { return 0; }\n',
    )
    with pytest.raises(CompileError,match='M5502') as raised:
        check(load_project(manifest))
    assert raised.value.span.source_name == str(tmp_path/'src'/'main.mrt')
    assert raised.value.span.line == 4
