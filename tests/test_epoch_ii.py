from pathlib import Path
import subprocess, tempfile
from merit.compiler import Checker, Interpreter, CGenerator, mir, parse
from merit.project.loader import load_project
from merit.project.build import interpret, build

ROOT=Path(__file__).parents[1]

def checked(source):
    p=parse(source); Checker(p).check(); return p

def test_string_and_owned_buffer_interpreter():
    p=checked('''module x
capability allocate;
fn main()->i32 { print("hi"); with capability allocate { let a:Allocator=system_allocator(); var b:Buffer=buffer_from_string(a,"ok"); buffer_push(b,33); print(b); drop(b); } return 0; }''')
    import io, contextlib
    out=io.StringIO()
    with contextlib.redirect_stdout(out): Interpreter(p).run()
    assert out.getvalue()=="hi\nok!\n"

def test_buffer_requires_allocate_capability():
    import pytest
    p=parse('''module x
fn main()->i32 { let a:Allocator=system_allocator(); let b:Buffer=buffer_new(a,8); return 0; }''')
    with pytest.raises(Exception, match='requires capabilities'):
        Checker(p).check()

def test_owned_buffer_moves():
    import pytest
    p=parse('''module x
capability allocate;
fn take(x:Buffer)->i32{return 0;}
fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_new(a,8); let x:i32=take(b); print(buffer_len(b)); } return 0; }''')
    with pytest.raises(Exception, match='moved'):
        Checker(p).check()

def test_cfg_mir_has_branch_and_loop_terminators():
    p=checked('''module x
fn main()->i32 { var x:i32=0; while x<2 { if x==1 { print(x); } else { print(0); } x=checked_add(x,1); } return 0; }''')
    kinds={b['terminator']['kind'] for b in mir(p)['functions'][0]['semantic_blocks']}
    assert {'branch','goto','return'} <= kinds

def test_cfg_mir_prunes_blocks_after_terminal_return():
    p=checked('''module x
fn main()->i32 { return 7; print(99); }''')
    blocks=mir(p)['functions'][0]['semantic_blocks']
    assert [block['id'] for block in blocks] == [0]
    assert blocks[0]['terminator']['kind'] == 'return'

def test_cfg_mir_folds_exact_constant_branches_before_pruning():
    p=checked('''module x
fn main()->i32 { if 2 * 3 == 7 { print(1); } else { print(2); } return 0; }''')
    blocks=mir(p)['functions'][0]['semantic_blocks']
    assert [block['id'] for block in blocks] == [0, 2, 3]
    assert blocks[0]['terminator']['kind'] == 'goto'
    assert blocks[0]['terminator']['target'] == 2
    assert blocks[0]['terminator']['folded_condition']['kind'] == 'binop'

def test_cfg_mir_constant_folding_uses_runtime_integer_literal_semantics():
    p=checked('''module x
fn main()->i32 { if 0.5 { print(1); } else { print(2); } return 0; }''')
    blocks=mir(p)['functions'][0]['semantic_blocks']
    assert [block['id'] for block in blocks] == [0, 2, 3]
    assert blocks[0]['terminator']['target'] == 2

def test_text_pipeline_project_native_matches():
    project=load_project(ROOT/'examples/projects/text_pipeline/Merit.toml')
    expected=interpret(project)
    assert expected=='Merit Epoch II\nabc!\n4\n327\n'
    with tempfile.TemporaryDirectory() as td:
        _,_,exe=build(project,Path(td)/'text_pipeline')
        actual=subprocess.run([str(exe)],capture_output=True,text=True,check=True).stdout
    assert actual==expected

def test_c_backend_emits_buffer_destructor():
    p=checked('''module x
capability allocate;
fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_new(a,8); } return 0; }''')
    c=CGenerator(p).generate()
    assert 'merit_buffer_drop(&b);' in c
