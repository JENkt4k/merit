import contextlib
import io

import pytest

from merit.compiler import Checker, CompileError, Interpreter, parse


def test_nonvoid_function_rejects_fallthrough():
    source='module missing_return\nfn missing()->i32 { print(1); }\nfn main()->i32 { return 0; }'
    with pytest.raises(CompileError,match='M3009: function missing does not return on every path'):
        Checker(parse(source)).check()


def test_if_requires_both_branches_to_return():
    source='module partial_return\nfn partial(value:i32)->i32 { if value == 1 { return 1; } else { print(0); } }\nfn main()->i32 { return 0; }'
    with pytest.raises(CompileError,match='M3009: function partial does not return on every path'):
        Checker(parse(source)).check()


def test_complete_if_is_a_definite_return():
    source='module complete_return\nfn choose(value:i32)->i32 { if value == 1 { return 1; } else { return 2; } }\nfn main()->i32 { print(choose(0)); return 0; }'
    program=parse(source);Checker(program).check()
    output=io.StringIO()
    with contextlib.redirect_stdout(output):Interpreter(program).run()
    assert output.getvalue() == '2\n'


def test_exhaustive_returning_match_is_a_definite_return():
    source='''module match_return
enum Choice { First, Second }
fn choose(value:Choice)->i32 { match (value) { First=>{ return 1; } Second=>{ return 2; } } }
fn main()->i32 { print(choose(Second())); return 0; }'''
    program=parse(source);Checker(program).check()
    output=io.StringIO()
    with contextlib.redirect_stdout(output):Interpreter(program).run()
    assert output.getvalue() == '2\n'
