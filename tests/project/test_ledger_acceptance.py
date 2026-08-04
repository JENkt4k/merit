import ctypes
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CompileError
from merit.project.build import build, build_shared, check, interpret
from merit.project.loader import load_project


ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'examples/projects/ledger_app/Merit.toml'
EXPECTED='1100.25\n2\n10\n1001\n1100.25\n'


def test_ledger_project_matches_interpreter_native_and_filesystem(tmp_path,monkeypatch):
    project=load_project(MANIFEST);checker=check(project)
    monkeypatch.chdir(tmp_path)
    assert interpret(project) == EXPECTED
    assert (tmp_path/'ledger_report.txt').read_text() == 'ledger-ok\n'
    (tmp_path/'ledger_report.txt').unlink()
    c_path,header,executable=build(project,tmp_path/'ledger_app')
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True,cwd=tmp_path).stdout
    assert native == EXPECTED
    assert (tmp_path/'ledger_report.txt').read_text() == 'ledger-ok\n'
    operations={(site['operation'],site['capability'],site['hazard']) for site in checker.hazardous_operations}
    assert ('buffer_from_string','allocate','allocation') in operations
    assert ('file_write','file_write','filesystem_write') in operations
    assert ('file_write','allocate','allocation') in operations
    generated=c_path.read_text()
    assert generated.index('merit_Buffer report = merit_buffer_from_string(') < generated.index('merit_FileWriteResult result = merit_file_write(')
    assert '_Static_assert(sizeof(merit_Account) == 16' in header.read_text()


def test_ledger_shared_library_has_stable_exact_decimal_abi(tmp_path):
    project=load_project(MANIFEST)
    _,header,library_path=build_shared(project,tmp_path/'libmerit_ledger')
    header_text=header.read_text()
    assert '_Static_assert(sizeof(merit_Account) == 16' in header_text
    assert '__builtin_offsetof(merit_Account, balance) == 8' in header_text
    assert 'int64_t merit_deposit(merit_Account *account, int64_t amount);' in header_text
    assert 'int64_t merit_account_balance(const merit_Account *account);' in header_text
    class Account(ctypes.Structure):
        _fields_=[('id',ctypes.c_uint64),('balance',ctypes.c_int64)]
    library=ctypes.CDLL(str(library_path))
    library.merit_deposit.argtypes=[ctypes.POINTER(Account),ctypes.c_int64]
    library.merit_deposit.restype=ctypes.c_int64
    library.merit_account_balance.argtypes=[ctypes.POINTER(Account)]
    library.merit_account_balance.restype=ctypes.c_int64
    account=Account(1001,100_000)
    assert library.merit_deposit(ctypes.byref(account),12_550) == 112_550
    assert library.merit_account_balance(ctypes.byref(account)) == 112_550
    assert account.balance == 112_550


def test_ledger_audit_export_requires_both_capabilities():
    project=load_project(MANIFEST)
    function=next(function for function in project.program.functions if function.name=='write_audit')
    function.requires_caps=[]
    with pytest.raises(CompileError,match=r'call to buffer_from_string requires capabilities'):
        check(project)
