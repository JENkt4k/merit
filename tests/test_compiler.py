from pathlib import Path
import subprocess
import pytest
from merit.compiler import BUILTIN_SIGS, CGenerator, VEC_INTRINSICS, audit_payload, parse, Checker, CompileError, Interpreter, compile_file

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
    assert BUILTIN_SIGS['file_write'].capability == 'file_write'
    assert BUILTIN_SIGS['file_write'].hazard == 'filesystem_write'
    assert VEC_INTRINSICS['new'].capability == 'allocate'
    assert VEC_INTRINSICS['new'].hazard == 'allocation'

def test_audit_reports_hazardous_builtin_operations():
    src='''module x
capability allocate;
fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_new(a,8); drop(b); } return 0; }'''
    p=parse(src); ch=Checker(p).check()
    audit=audit_payload(p,ch)
    assert audit['sites'] == [{'function':'main','capability':'allocate'}]
    assert audit['hazardous_operations'] == [{'function':'main','operation':'buffer_new','capability':'allocate','hazard':'allocation','hazard_class':'allocation','review':'memory-resource','scope':'lexical'}]
    requirements = {(entry['kind'], entry['operation'], entry['capability'], entry['hazard']) for entry in audit['capability_requirements']}
    assert ('builtin', 'buffer_new', 'allocate', 'allocation') in requirements
    assert ('builtin', 'file_read', 'file_read', 'filesystem_read') in requirements
    assert ('builtin', 'file_write', 'file_write', 'filesystem_write') in requirements
    assert ('vector_intrinsic', 'vec_new<T>', 'allocate', 'allocation') in requirements
    policies = {(entry['capability'], entry['hazard_class'], entry['review'], entry['scope']) for entry in audit['capability_policies']}
    assert ('allocate', 'allocation', 'memory-resource', 'lexical') in policies

def test_audit_reports_user_declared_capability_requirements():
    p=parse((ROOT/'examples/account_component.mrt').read_text())
    audit=audit_payload(p,Checker(p).check())
    requirements = {(entry['kind'], entry['operation'], entry['capability'], entry['hazard'], entry['hazard_class']) for entry in audit['capability_requirements']}
    assert ('function', 'native_notice', 'foreign_call', 'user_declared', 'foreign_call') in requirements

def test_file_write_requires_specific_capability():
    src='''module x
capability allocate;
capability file_write;
fn main()->i32 { with capability allocate { let a:Allocator=system_allocator(); let b:Buffer=buffer_from_string(a,"abc"); print(file_write("out.bin", b)); drop(b); } return 0; }'''
    with pytest.raises(CompileError, match='requires capabilities'):
        Checker(parse(src)).check()

def test_file_write_interpreter_and_native_match(tmp_path):
    target = (tmp_path / 'written.bin').as_posix()
    src=f'''module x
capability allocate;
capability file_write;
fn main()->i32 {{
    with capability allocate {{
        let a:Allocator=system_allocator();
        let b:Buffer=buffer_from_string(a,"abc");
        with capability file_write {{
            let written:FileWriteResult=file_write("{target}", b);
            match(written) {{ WriteOk(count)=>{{print(count);}} WriteErr(error)=>{{print(0);}} }}
        }}
        drop(b);
    }}
    return 0;
}}'''
    p=parse(src); ch=Checker(p).check()
    assert Interpreter(p).run().value == 0
    assert (tmp_path / 'written.bin').read_bytes() == b'abc'
    audit=audit_payload(p,ch)
    operations = {(entry['operation'], entry['capability'], entry['hazard'], entry['hazard_class']) for entry in audit['hazardous_operations']}
    assert ('file_write', 'file_write', 'filesystem_write', 'filesystem_write') in operations
    exe=tmp_path/'file_write'
    source=tmp_path/'file_write.mrt'
    source.write_text(src)
    compile_file(source,exe)
    native=subprocess.run([str(exe)],check=True,text=True,capture_output=True)
    assert native.stdout == '3\n'
    assert (tmp_path / 'written.bin').read_bytes() == b'abc'


def test_typed_filesystem_failures_match_interpreter_and_native(tmp_path, capsys):
    missing = (tmp_path / 'missing.bin').as_posix()
    directory = tmp_path.as_posix()
    src=f'''module typed_filesystem_errors
capability allocate;
capability file_read;
capability file_write;
fn main()->i32 {{
    with capability allocate {{
        let allocator:Allocator=system_allocator();
        with capability file_read {{
            let read:FileReadResult=file_read(allocator,"{missing}");
            match(read) {{
                ReadOk(data)=>{{print(0);drop(data);}}
                ReadErr(error)=>{{match(error) {{ FsNotFound=>{{print(1);}} FsPermissionDenied=>{{print(2);}} FsIoError=>{{print(3);}} }}}}
            }}
        }}
        let data:Buffer=buffer_from_string(allocator,"abc");
        with capability file_write {{
            let written:FileWriteResult=file_write("{directory}",data);
            match(written) {{
                WriteOk(count)=>{{print(count);}}
                WriteErr(error)=>{{match(error) {{ FsNotFound=>{{print(1);}} FsPermissionDenied=>{{print(2);}} FsIoError=>{{print(3);}} }}}}
            }}
        }}
        drop(data);
    }}
    return 0;
}}'''
    program=parse(src);Checker(program).check();Interpreter(program).run()
    interpreted=capsys.readouterr().out
    source=tmp_path/'typed_filesystem_errors.mrt';executable=tmp_path/'typed_filesystem_errors'
    source.write_text(src);compile_file(source,executable)
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    assert interpreted == native == '1\n3\n'

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
