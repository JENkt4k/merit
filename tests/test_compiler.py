from pathlib import Path
import pytest
from merit.compiler import parse, Checker, CompileError, Interpreter

ROOT=Path(__file__).parents[1]

def test_ledger_checks():
    p=parse((ROOT/'examples/ledger.mrt').read_text())
    ch=Checker(p).check()
    assert ch.audit_sites == [{'function':'main','capability':'foreign_call'}]

def test_decimal_scale_rejected():
    p=parse((ROOT/'examples/invalid_rounding.mrt').read_text())
    with pytest.raises(CompileError, match='explicit rounding required'):
        Checker(p).check()

def test_bounded_rejected():
    src='''module x\nbounded Month(u8,1,12);\nfn main()->i32 { let m: Month = 13; return 0; }'''
    with pytest.raises(CompileError, match='outside Month range'):
        Checker(parse(src)).check()
