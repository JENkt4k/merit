import pytest

from merit.compiler import Checker, CompileError, hir, parse


def source(signature: str, body: str) -> str:
    return f'''module borrowed_returns
stable("v1") struct Value {{ number: i32; }}
fn expose({signature}) -> borrow Value {{ {body} }}
fn main() -> i32 {{ return 0; }}'''


def test_borrowed_return_syntax_is_explicit_in_hir():
    program = parse(source("borrow value: Value", "return value;"))
    function = hir(program)["functions"][0]
    assert function["return"] == "Value"
    assert function["return_mode"] == "borrow"


def test_borrowed_return_requires_borrowed_parameter_origin():
    program = parse(source("value: Value", "return value;"))
    with pytest.raises(CompileError, match="M5300: borrowed return must originate from a borrowed parameter"):
        Checker(program).check()


def test_mutable_borrowed_return_requires_mutable_borrow_parameter():
    program = parse(source("borrow value: Value", "return value;").replace("-> borrow Value", "-> borrow_mut Value"))
    with pytest.raises(CompileError, match="M5301: borrow_mut return requires borrow_mut parameter value"):
        Checker(program).check()


def test_valid_borrow_origin_waits_for_caller_lifetime_lowering():
    program = parse(source("borrow value: Value", "return value;"))
    with pytest.raises(CompileError, match="M5302: borrowed return lowering requires caller lifetime tracking"):
        Checker(program).check()
