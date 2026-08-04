import pytest

from merit.compiler import Checker, CompileError, hir, mir, parse


PREFIX='''module ephemeral_boundary
stable("value-v1") struct Value { number:i32; }
struct Holder { value:Value; }
enum Wrapped { Some(Value), None }
enum Choice { First, Second }
fn expose(borrow value:Value)->borrow Value { return value; }
fn expose_number(borrow value:i32)->borrow i32 { return value; }
fn expose_choice(borrow value:Choice)->borrow Choice { return value; }
fn observe(borrow value:Value)->i32 { return value.number; }
'''


@pytest.mark.parametrize(('body','message'),[
    ('let value:Value=Value{number:1}; let holder:Holder=Holder{value:expose(value)}; return 0;', 'borrowed return cannot be stored in field Holder.value'),
    ('let value:Value=Value{number:1}; let wrapped:Wrapped=Some(expose(value)); return 0;', 'borrowed return cannot be stored in enum payload Wrapped::Some'),
    ('let choice:Choice=First(); match (expose_choice(choice)) { First=>{ print(1); } Second=>{ print(2); } } return 0;', 'borrowed return cannot be used as a match subject'),
    ('let value:i32=1; print(expose_number(value)); return 0;', 'borrowed return cannot be used as a printed value'),
    ('let value:i32=1; if expose_number(value) { print(1); } return 0;', 'borrowed return cannot be used as a condition'),
    ('let value:i32=1; expose_number(value); return 0;', 'borrowed return cannot be used as a discarded value'),
    ('let value:i32=1; return expose_number(value)+1;', 'borrowed return cannot be used as a binary operand'),
])
def test_borrowed_results_cannot_escape_ephemeral_contexts(body,message):
    with pytest.raises(CompileError,match=message):
        Checker(parse(PREFIX+f'fn main()->i32 {{ {body} }}')).check()


def test_ephemeral_field_access_and_borrow_forwarding_remain_valid():
    source=PREFIX+'''fn main()->i32 {
        let value:Value=Value{number:17};
        print(expose(value).number);
        return observe(expose(value));
    }'''
    Checker(parse(source)).check()


def test_hir_and_mir_publish_the_alpha_borrow_policy():
    program=parse(PREFIX+'fn main()->i32 { return 0; }');Checker(program).check()
    expected={'returned_borrows':'ephemeral','stored_references':False,'lifetime_parameters':False}
    assert hir(program)['borrow_policy'] == expected
    assert mir(program)['borrow_policy'] == expected
