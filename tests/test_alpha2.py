from pathlib import Path
import pytest
from merit.compiler import parse, Checker, CompileError, LayoutEngine, Interpreter, CGenerator
ROOT=Path(__file__).parents[1]

def src(): return (ROOT/'examples/account_component.mrt').read_text()

def test_struct_layout_stable():
    p=parse(src()); Checker(p).check(); lay=LayoutEngine(p).all()[0]
    assert lay['abi']=='merit-v1'
    assert lay['size']==16
    assert [f['offset'] for f in lay['fields']]==[0,8]
    assert len(lay['layout_hash'])==24

def test_capability_propagation_rejected():
    bad=src().replace('with capability foreign_call {\n        print(native_notice());\n    }','print(native_notice());')
    with pytest.raises(CompileError,match='requires capabilities'):
        Checker(parse(bad)).check()

def test_move_rejected():
    bad='''module x\nstable("v1") struct S { x:i32; }\nfn main()->i32 { let a:S=S{x:1}; let b:S=a; print(a.x); return 0; }'''
    with pytest.raises(CompileError,match='moved value'):
        Checker(parse(bad)).check()

def test_header_generation():
    h=CGenerator(parse(src())).header()
    assert 'typedef struct merit_Account' in h
    assert 'int64_t balance;' in h
