import contextlib
import io
import subprocess

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, compile_file, hir, mir, parse


SHADOWING_PROGRAM='''module binding_identity
struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn consume(value:Marker)->i32 {
    let value:Marker=Marker{number:2};
    drop(value);
    return 0;
}
fn main()->i32 {
    let marker:Marker=Marker{number:1};
    if 1 { let marker:Marker=Marker{number:3}; drop(marker); }
    let argument:Marker=Marker{number:4};
    consume(argument);
    drop(marker);
    return 0;
}'''


def test_shadowed_bindings_keep_distinct_ownership_and_c_names(tmp_path):
    program=parse(SHADOWING_PROGRAM);Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    source=tmp_path/'binding_identity.mrt';source.write_text(SHADOWING_PROGRAM)
    _,c_path,_,executable=compile_file(source,tmp_path/'binding_identity')
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    assert interpreted.getvalue() == native == '3\n2\n4\n1\n'
    generated=c_path.read_text()
    assert 'merit_Marker value__b' in generated
    assert 'merit_Marker marker__b' in generated


def test_hir_and_mir_expose_unique_binding_ids():
    program=parse(SHADOWING_PROGRAM);Checker(program).check()
    main_hir=hir(program)['functions'][1]
    outer=main_hir['body'][0]['binding_id']
    inner=main_hir['body'][1]['operands'][1][0]['binding_id']
    assert outer['name'] == inner['name'] == 'marker'
    assert outer['serial'] != inner['serial']
    bindings=mir(program)['functions'][1]['owned_bindings']
    assert len({binding['serial'] for binding in bindings}) == len(bindings)


def test_use_after_drop_targets_the_innermost_shadow():
    source='''module invalid_shadow_use
struct Marker { number:i32; }
fn main()->i32 { let marker:Marker=Marker{number:1}; if 1 { let marker:Marker=Marker{number:2}; drop(marker); print(marker.number); } drop(marker); return 0; }'''
    with pytest.raises(CompileError,match='M5103: use of dropped value marker'):
        Checker(parse(source)).check()


def test_binding_does_not_escape_its_lexical_scope():
    source='''module invalid_scope_escape
fn main()->i32 { if 1 { let value:i32=2; print(value); } print(value); return 0; }'''
    with pytest.raises(CompileError,match='M3003: unknown variable value'):
        Checker(parse(source)).check()
