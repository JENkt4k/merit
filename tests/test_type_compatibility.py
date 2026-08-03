import pytest

from merit.compiler import Checker, CompileError, parse


@pytest.mark.parametrize(
    ('source','message'),
    [
        ('module literal_binding\nfn main()->i32 { let value:Allocator=1; return 0; }','M3001: cannot assign number to Allocator'),
        ('module literal_assignment\nfn main()->i32 { var value:Allocator=system_allocator(); value=1; return 0; }','M3006: cannot assign number to Allocator'),
        ('module literal_return\nfn invalid()->Allocator { return 1; }\nfn main()->i32 { return 0; }','M3002: return type number does not match Allocator'),
        ('module literal_field\nstruct Holder { value:Allocator; }\nfn main()->i32 { let holder:Holder=Holder{value:1}; return 0; }','M4006: field value expects Allocator'),
        ('module literal_variant\nenum MaybeAllocator { Some(Allocator), None }\nfn main()->i32 { let value:MaybeAllocator=Some(1); return 0; }','M6004: Some expects Allocator'),
    ],
)
def test_numeric_literals_do_not_cross_nonnumeric_value_boundaries(source,message):
    with pytest.raises(CompileError,match=message):
        Checker(parse(source)).check()


def test_bounded_literal_is_validated_at_user_call_boundary():
    source='''module bounded_call
bounded Count(i32,0,2);
fn accept(value:Count)->Count { return value; }
fn main()->i32 { accept(3); return 0; }'''
    with pytest.raises(CompileError,match='M1103: 3 outside Count range 0..2'):
        Checker(parse(source)).check()


def test_bounded_literal_is_validated_at_vector_boundary():
    source='''module bounded_vector
capability allocate;
bounded Count(i32,0,2);
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var values:Vec<Count>=vec_new<Count>(allocator,1); vec_push<Count>(values,3); } return 0; }'''
    with pytest.raises(CompileError,match='M1103: 3 outside Count range 0..2'):
        Checker(parse(source)).check()
