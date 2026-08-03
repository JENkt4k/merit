from pathlib import Path
import subprocess
import pytest
from merit.compiler import parse, Checker, CompileError, Interpreter, CGenerator, mir, compile_file


def checked(src: str):
    p=parse(src); Checker(p).check(); return p


def run_failure_parity(src: str, tmp_path: Path, name: str):
    p=checked(src)
    with pytest.raises(RuntimeError) as interpreted:
        Interpreter(p).run()
    path=tmp_path/f'{name}.mrt'; path.write_text(src)
    exe=tmp_path/name; compile_file(path,exe)
    native=subprocess.run([str(exe)],text=True,capture_output=True)
    return str(interpreted.value), native


def test_conflicting_mutable_and_shared_loans_rejected():
    src='''module x
stable("v1") struct S { x:i32; }
fn collide(borrow_mut a:S, borrow b:S)->i32 { return a.x; }
fn main()->i32 { var s:S=S{x:1}; return collide(s,s); }'''
    with pytest.raises(CompileError, match='conflicting loans'):
        Checker(parse(src)).check()


def test_mutable_borrow_requires_mutable_binding():
    src='''module x
stable("v1") struct S { x:i32; }
fn alter(borrow_mut a:S)->i32 { a.x=2; return a.x; }
fn main()->i32 { let s:S=S{x:1}; return alter(s); }'''
    with pytest.raises(CompileError, match='not mutable'):
        Checker(parse(src)).check()


def test_use_after_explicit_drop_rejected():
    src='''module x
stable("v1") struct S { x:i32; }
fn main()->i32 { let s:S=S{x:1}; drop(s); return s.x; }'''
    with pytest.raises(CompileError, match='dropped value'):
        Checker(parse(src)).check()


def test_drop_of_borrowed_parameter_rejected():
    src='''module x
stable("v1") struct S { x:i32; }
fn bad(borrow s:S)->i32 { drop(s); return 0; }
fn main()->i32 { let s:S=S{x:1}; return bad(s); }'''
    with pytest.raises(CompileError, match='cannot drop borrowed'):
        Checker(parse(src)).check()


def test_owned_field_move_to_binding_rejected():
    src='''module x
capability allocate;
struct OwnedText { data: Buffer; }
fn main()->i32 {
    with capability allocate {
        let a:Allocator=system_allocator();
        let b:Buffer=buffer_from_string(a,"abc");
        let wrapped:OwnedText=OwnedText{data:b};
        let out:Buffer=wrapped.data;
        drop(out);
    }
    return 0;
}'''
    with pytest.raises(CompileError, match='cannot move owned field wrapped\\.data'):
        Checker(parse(src)).check()


def test_owned_field_move_to_call_rejected():
    src='''module x
capability allocate;
struct OwnedText { data: Buffer; }
fn take(x:Buffer)->i32 { drop(x); return 0; }
fn main()->i32 {
    with capability allocate {
        let a:Allocator=system_allocator();
        let b:Buffer=buffer_from_string(a,"abc");
        let wrapped:OwnedText=OwnedText{data:b};
        return take(wrapped.data);
    }
    return 0;
}'''
    with pytest.raises(CompileError, match='cannot move owned field wrapped\\.data'):
        Checker(parse(src)).check()


def test_owned_field_move_to_struct_init_rejected():
    src='''module x
capability allocate;
struct OwnedText { data: Buffer; }
struct Outer { data: Buffer; }
fn main()->i32 {
    with capability allocate {
        let a:Allocator=system_allocator();
        let b:Buffer=buffer_from_string(a,"abc");
        let wrapped:OwnedText=OwnedText{data:b};
        let outer:Outer=Outer{data:wrapped.data};
        drop(outer);
    }
    return 0;
}'''
    with pytest.raises(CompileError, match='cannot move owned field wrapped\\.data'):
        Checker(parse(src)).check()


def test_owned_field_return_rejected():
    src='''module x
capability allocate;
struct OwnedText { data: Buffer; }
fn unwrap(wrapped:OwnedText)->Buffer { return wrapped.data; }
fn main()->i32 {
    with capability allocate {
        let a:Allocator=system_allocator();
        let b:Buffer=buffer_from_string(a,"abc");
        let wrapped:OwnedText=OwnedText{data:b};
        let out:Buffer=unwrap(wrapped);
        drop(out);
    }
    return 0;
}'''
    with pytest.raises(CompileError, match='cannot move owned field wrapped\\.data'):
        Checker(parse(src)).check()


def test_owned_assignment_rejected_until_replace_semantics_exist():
    src='''module x
capability allocate;
fn main()->i32 {
    with capability allocate {
        let a:Allocator=system_allocator();
        var first:Buffer=buffer_from_string(a,"abc");
        let second:Buffer=buffer_from_string(a,"def");
        first = second;
        drop(first);
    }
    return 0;
}'''
    with pytest.raises(CompileError, match='cannot assign into owned storage first'):
        Checker(parse(src)).check()


def test_mir_inserts_reverse_implicit_drops():
    src='''module x
stable("v1") struct S { x:i32; }
fn main()->i32 { let a:S=S{x:1}; let b:S=S{x:2}; return 0; }'''
    p=checked(src)
    statements=mir(p)['functions'][0]['semantic_blocks'][0]['statements']
    assert statements[-2:]==[['drop_implicit','b'],['drop_implicit','a']]


def test_c_backend_uses_pointers_for_borrows():
    src='''module x
stable("v1") struct S { x:i32; }
fn alter(borrow_mut s:S)->i32 { s.x=2; return s.x; }
fn main()->i32 { var s:S=S{x:1}; return alter(s); }'''
    c=CGenerator(checked(src)).generate()
    assert 'merit_alter(merit_S *s)' in c
    assert 'int32_t _merit_assign_value_0 = 2;' in c
    assert 'int32_t *_merit_assign_address_0 = &s->x;' in c
    assert '*_merit_assign_address_0 = _merit_assign_value_0;' in c
    assert 'merit_alter(&s)' in c


def test_postcondition_result_and_old_interpreter():
    src='''module x
fn inc(x:i32)->i32 ensures result == old(x) + 1; { return x + 1; }
fn main()->i32 { return inc(4); }'''
    p=checked(src)
    assert Interpreter(p).run().value==5


def test_contracts_must_be_boolean():
    src='''module x
fn id(x:i32)->i32 requires "not boolean"; { return x; }
fn main()->i32 { return id(1); }'''
    with pytest.raises(CompileError, match='precondition must be boolean'):
        checked(src)


@pytest.mark.parametrize('clause',["requires mutate(value) > 0;","ensures mutate(value) > 0;"])
def test_contracts_reject_mutating_calls(clause):
    src=f'''module contract_purity
stable("v1") struct Value {{ number:i32; }}
fn mutate(borrow_mut value:Value)->i32 {{ value.number=value.number+1; return value.number; }}
fn inspect(borrow_mut value:Value)->i32 {clause} {{ return value.number; }}
fn main()->i32 {{ var value:Value=Value{{number:1}}; return inspect(value); }}'''
    with pytest.raises(CompileError,match='M3203: .*condition cannot call impure function mutate'):
        checked(src)


def test_contracts_reject_hazardous_builtin_calls():
    src='''module contract_hazard
capability allocate;
fn create(allocator:Allocator)->i32 requires buffer_len(buffer_new(allocator,1)) == 0; { return 0; }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); return create(allocator); } }'''
    with pytest.raises(CompileError,match='M3203: precondition cannot call mutating or hazardous operation buffer_new'):
        checked(src)


def test_contracts_reject_mutating_vector_intrinsics():
    src='''module contract_vector_mutation
capability allocate;
fn inspect(borrow_mut values:Vec<i64>)->i32 requires vec_push<i64>(values,1) == 0; { return 0; }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var values:Vec<i64>=vec_new<i64>(allocator,0); return inspect(values); } }'''
    with pytest.raises(CompileError,match='M3203: precondition cannot call mutating or hazardous operation vec_push'):
        checked(src)


def test_contracts_allow_read_only_function_calls(tmp_path):
    src='''module contract_observation
fn positive(value:i32)->i32 { return value > 0; }
fn identity(value:i32)->i32 requires positive(value) == 1; ensures positive(result) == 1; { return value; }
fn main()->i32 { return identity(7); }'''
    program=checked(src)
    assert Interpreter(program).run().value==7
    source=tmp_path/'contract_observation.mrt';executable=tmp_path/'contract_observation'
    source.write_text(src);compile_file(source,executable)
    assert subprocess.run([str(executable)]).returncode==7


def test_contracts_reject_transitively_impure_unannotated_helpers():
    src='''module contract_transitive_impurity
fn noisy(value:i32)->i32 { print(value); return value; }
fn wrapper(value:i32)->i32 { return noisy(value); }
fn identity(value:i32)->i32 requires wrapper(value) > 0; { return value; }
fn main()->i32 { return identity(1); }'''
    with pytest.raises(CompileError,match='M3203: precondition cannot call impure function wrapper'):
        checked(src)


def test_contracts_reject_helpers_with_observable_owned_cleanup():
    src='''module contract_cleanup_impurity
struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn observe(value:i32)->i32 { let marker:Marker=Marker{number:value}; return value; }
fn identity(value:i32)->i32 requires observe(value) > 0; { return value; }
fn main()->i32 { return identity(1); }'''
    with pytest.raises(CompileError,match='M3203: precondition cannot call impure function observe'):
        checked(src)


def test_old_is_postcondition_only():
    pre='''module x
fn id(x:i32)->i32 requires old(x) == x; { return x; }
fn main()->i32 { return id(1); }'''
    body='''module x
fn main()->i32 { return old(1); }'''
    with pytest.raises(CompileError, match='old\\(\\) is only valid in postconditions'):
        checked(pre)
    with pytest.raises(CompileError, match='old\\(\\) is only valid in postconditions'):
        checked(body)


def test_old_rejects_shallow_snapshots_of_owned_values():
    src='''module owned_old_snapshot
fn length(borrow value:Buffer)->i64 ensures buffer_len(old(value)) == result; { return buffer_len(value); }
fn main()->i32 { return 0; }'''
    with pytest.raises(CompileError,match='M3204: old\\(\\) requires a Copy value, got Buffer'):
        checked(src)


def test_contract_failure_interpreter_and_native_are_deterministic(tmp_path):
    src='''module x
fn inc(x:i32)->i32 ensures result == old(x) + 2; { return x + 1; }
fn main()->i32 { return inc(4); }'''
    interpreted, native = run_failure_parity(src,tmp_path,'contract_fail')
    assert interpreted == 'postcondition failed in inc'
    assert native.returncode == 73
    assert native.stdout == ''
    assert 'postcondition failed in inc' in native.stderr


def test_precondition_failure_interpreter_and_native_are_deterministic(tmp_path):
    src='''module x
fn positive(x:i32)->i32 requires x > 0; { return x; }
fn main()->i32 { return positive(0); }'''
    interpreted, native = run_failure_parity(src,tmp_path,'precondition_fail')
    assert interpreted == 'precondition failed in positive'
    assert native.returncode == 71
    assert native.stdout == ''
    assert 'precondition failed in positive' in native.stderr


def test_native_and_interpreter_match_for_borrowed_mutation(tmp_path):
    src='''module x
stable("v1") struct S { x:i32; }
fn alter(borrow_mut s:S)->i32 { s.x=7; return s.x; }
fn main()->i32 { var s:S=S{x:1}; print(alter(s)); print(s.x); return 0; }'''
    path=tmp_path/'x.mrt'; path.write_text(src)
    p=checked(src)
    exe=tmp_path/'x'
    compile_file(path,exe)
    native=subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout
    assert native=='7\n7\n'
