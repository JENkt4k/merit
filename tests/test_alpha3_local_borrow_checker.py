"""Executable RM1 straight-line checker contract."""

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, OwnershipEffects, TypeTable, parse


def check(body: str, *, declarations: str = "", functions: str = "") -> None:
    program = parse(f"module rm1\n{declarations}\n{functions}\nfn main()->i32 {{ {body} return 0; }}")
    Checker(program).check()


@pytest.mark.parametrize(
    ("case", "body", "declarations", "functions"),
    [
        ("01", 'let x:String="a"; let r: borrow String = borrow x; print(r);', "", ""),
        ("02", 'let x:String="a"; let r: borrow String = borrow x; let s: borrow String = borrow x; print(r); print(s);', "", ""),
        ("04", 'var x:i32=1; let r: borrow i32 = borrow x; print(r); x=2;', "", ""),
        ("07", 'let x:Box=Box {value:1}; let r: borrow Box = borrow x; print(r.value); let y:Box=x; print(y.value);', 'struct Box { value:i32; }', ""),
        ("09", 'let x:String="a"; let r: borrow String = borrow x; print(r); drop(x);', "", ""),
        ("18", 'var x:i32=1; with capability io { let r: borrow i32 = borrow x; print(r); } x=2;', 'capability io;', ""),
        ("24", 'let x:i32=1; let r: borrow i32 = borrow x; inspect(r); print(r);', "", 'fn inspect(borrow value:i32)->i32 { return value; }'),
    ],
)
def test_required_acceptance(case: str, body: str, declarations: str, functions: str) -> None:
    check(body, declarations=declarations, functions=functions)


@pytest.mark.parametrize(
    ("case", "body", "declarations", "diagnostic"),
    [
        ("05", 'var x:i32=1; let r: borrow i32 = borrow x; x=2; print(r);', "", "M5402"),
        ("06", 'let x:Box=Box {value:1}; let r: borrow Box = borrow x; let y:Box=x; print(r.value);', 'struct Box { value:i32; }', "M5402"),
        ("08", 'let x:String="a"; let r: borrow String = borrow x; drop(x); print(r);', "", "M5402"),
        ("22", 'let x:i32=1; let r: borrow i32 = borrow x; return r;', "", "M5404"),
        ("23", 'let x:i32=1; let r: borrow i32 = borrow x; let h:Holder=Holder {value:r};', 'struct Holder { value:i32; }', "M5404"),
        ("28", 'let x:String="a"; let r: borrow String = borrow x; replace(x,"b"); print(r);', "", "M5402"),
    ],
)
def test_required_rejection(case: str, body: str, declarations: str, diagnostic: str) -> None:
    with pytest.raises(CompileError, match=diagnostic):
        check(body, declarations=declarations)


def test_two_shared_loans_keep_owner_locked_until_both_final_uses() -> None:
    check('var x:i32=1; let a: borrow i32 = borrow x; let b: borrow i32 = borrow x; print(a); print(b); x=2;')
    with pytest.raises(CompileError, match="M5402"):
        check('var x:i32=1; let a: borrow i32 = borrow x; let b: borrow i32 = borrow x; print(a); x=2; print(b);')


def test_replacement_after_last_use_preserves_owner_cleanup_authority() -> None:
    declarations='struct Box { value:i32; } destructor Box { print(9); }'
    check('var x:Box=Box {value:1}; let r: borrow Box = borrow x; print(r.value); replace(x,Box {value:2});', declarations=declarations)


def test_borrowed_parameter_origin_is_accepted_without_escape() -> None:
    program=parse('module rm1\nstruct Box { value:i32; }\n'
                  'fn inspect(borrow x:Box)->i32 { let r: borrow Box = borrow x; return r.value; }\n'
                  'fn main()->i32 { let x:Box=Box {value:1}; return inspect(x); }')
    Checker(program).check()


@pytest.mark.parametrize(
    ("body", "diagnostic"),
    [
        ('let r: borrow i32 = borrow missing;', 'M5401'),
        ('let x:i32=1; let r: borrow i32 = borrow x; drop(r);', 'M5403'),
        ('var x:i32=1; let r: borrow i32 = borrow x; if 1 { print(r); }', 'M5403'),
        ('let x:i32=1; let r: borrow i32 = borrow x; consume(r);', 'M5403'),
        ('let x:i32=1; let r: borrow i32 = borrow x; relay(r);', 'M5403'),
    ],
)
def test_invalid_origin_use_control_flow_and_call_effects_fail_closed(body: str, diagnostic: str) -> None:
    functions=('fn consume(x:i32)->i32 { return x; }\n'
               'fn relay(borrow x:i32)->borrow i32 { return x; }')
    with pytest.raises(CompileError, match=diagnostic):
        check(body, functions=functions)


def test_backend_entry_remains_fail_closed_during_checker_phase() -> None:
    program=parse('module rm1\nfn main()->i32 { let x:i32=1; let r: borrow i32 = borrow x; print(r); return 0; }')
    Checker(program).check()
    with pytest.raises(CompileError, match='M5400'):
        Interpreter(program)
    with pytest.raises(CompileError, match='M5400'):
        CGenerator(program)


def test_unsupported_nested_control_flow_fails_closed() -> None:
    with pytest.raises(CompileError, match='M5403'):
        check('var x:i32=1; if 1 { let r: borrow i32 = borrow x; print(r); }')


def test_local_reference_cannot_escape_borrowed_return() -> None:
    program=parse('module rm1\nfn leak(borrow x:i32)->borrow i32 { '
                  'let r: borrow i32 = borrow x; return r; }\n'
                  'fn main()->i32 { return 0; }')
    with pytest.raises(CompileError, match='M5404'):
        Checker(program).check()


def test_conflict_diagnostic_points_to_loan_creation() -> None:
    program=parse('module rm1\nfn main()->i32 { var x:i32=1; '
                  'let r: borrow i32 = borrow x; x=2; print(r); return 0; }')
    with pytest.raises(CompileError) as caught:
        Checker(program).check()
    assert caught.value.code=='M5402'
    assert caught.value.span is not None
    assert any(note.span is not None and 'created' in note.message for note in caught.value.notes)


def test_byteslice_origin_is_deferred_until_backing_owner_is_proven() -> None:
    program=parse('module rm1\nfn inspect(borrow source:ByteSlice)->i32 { '
                  'let r: borrow ByteSlice = borrow source; return 0; }\n'
                  'fn main()->i32 { return 0; }')
    with pytest.raises(CompileError, match='M5401'):
        Checker(program).check()


def test_owned_origin_cannot_move_through_nested_aggregate_before_final_use() -> None:
    declarations='struct Box { value:i32; } struct Holder { item:Box; }'
    with pytest.raises(CompileError, match='M5402'):
        check('let x:Box=Box {value:1}; let r: borrow Box = borrow x; '
              'let h:Holder=Holder {item:x}; print(r.value);', declarations=declarations)


def test_owned_origin_cannot_move_into_enum_before_final_use() -> None:
    declarations='struct Box { value:i32; } enum Choice { Some(Box), None }'
    with pytest.raises(CompileError, match='M5402'):
        check('let x:Box=Box {value:1}; let r: borrow Box = borrow x; '
              'let choice:Choice=Some(x); print(r.value);', declarations=declarations)


def test_ephemeral_mutable_borrow_conflicts_with_stored_shared_loan() -> None:
    functions='fn mutate(borrow_mut x:i32)->i32 { x=2; return x; }'
    with pytest.raises(CompileError, match='M5402'):
        check('var x:i32=1; let r: borrow i32 = borrow x; mutate(x); print(r);', functions=functions)


def test_implicit_cleanup_remains_exclusively_with_owner() -> None:
    program=parse('module rm1\nstruct Box { value:i32; } destructor Box { print(9); }\n'
                  'fn main()->i32 { let x:Box=Box {value:1}; '
                  'let r: borrow Box = borrow x; print(r.value); return 0; }')
    Checker(program).check()
    owned=OwnershipEffects(program,TypeTable(program)).function(program.functions[0]).owned_locals
    assert [binding.name for binding,_ in owned]==['x']
