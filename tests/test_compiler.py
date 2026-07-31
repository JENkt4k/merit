from pathlib import Path
import pytest
from merit.compiler import BUILTIN_SIGS, CGenerator, VEC_INTRINSICS, audit_payload, parse, Checker, CompileError, Interpreter

ROOT=Path(__file__).parents[1]

def test_ledger_checks():
    p=parse((ROOT/'examples/ledger.mrt').read_text())
    ch=Checker(p).check()
    assert ch.audit_sites == [{'function':'main','capability':'foreign_call'}]

def test_builtin_hazard_metadata_is_explicit():
    assert BUILTIN_SIGS['buffer_new'].capability == 'allocate'
    assert BUILTIN_SIGS['buffer_new'].hazard == 'allocation'
    assert BUILTIN_SIGS['file_read'].capability == 'file_read'
    assert BUILTIN_SIGS['file_read'].hazard == 'filesystem_read'
    assert VEC_INTRINSICS['new'].capability == 'allocate'
    assert VEC_INTRINSICS['new'].hazard == 'allocation'

def test_audit_reports_hazardous_builtin_operations():
    src='''module x
capability allocate;
fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_new(a,8); drop(b); } return 0; }'''
    p=parse(src); ch=Checker(p).check()
    audit=audit_payload(p,ch)
    assert audit['sites'] == [{'function':'main','capability':'allocate'}]
    assert audit['hazardous_operations'] == [{'function':'main','operation':'buffer_new','capability':'allocate','hazard':'allocation'}]
    requirements = {(entry['kind'], entry['operation'], entry['capability'], entry['hazard']) for entry in audit['capability_requirements']}
    assert ('builtin', 'buffer_new', 'allocate', 'allocation') in requirements
    assert ('builtin', 'file_read', 'file_read', 'filesystem_read') in requirements
    assert ('vector_intrinsic', 'vec_new<T>', 'allocate', 'allocation') in requirements

def test_audit_reports_user_declared_capability_requirements():
    p=parse((ROOT/'examples/account_component.mrt').read_text())
    audit=audit_payload(p,Checker(p).check())
    assert {'kind':'function','operation':'native_notice','capability':'foreign_call','hazard':'user_declared'} in audit['capability_requirements']

def test_generated_c_marks_capability_boundaries():
    c=CGenerator(parse((ROOT/'examples/ledger.mrt').read_text())).generate()
    assert '/* merit capability begin: foreign_call */' in c
    assert '/* merit capability end: foreign_call */' in c

def test_decimal_scale_rejected():
    p=parse((ROOT/'examples/invalid_rounding.mrt').read_text())
    with pytest.raises(CompileError, match='explicit rounding required'):
        Checker(p).check()

def test_bounded_rejected():
    src='''module x\nbounded Month(u8,1,12);\nfn main()->i32 { let m: Month = 13; return 0; }'''
    with pytest.raises(CompileError, match='outside Month range'):
        Checker(parse(src)).check()
