"""RM1 parser compatibility before semantic lowering is enabled."""

import pytest

from merit.compiler import Checker, parse


def test_local_borrow_form_has_distinct_node_and_origin_binding() -> None:
    program = parse(
        "module m\n"
        "struct Box { value:i32; }\n"
        "fn main()->i32 { let x:Box=Box {value:1}; "
        "let r: borrow Box = borrow x; return x.value; }"
    )
    binding = program.functions[0].body[1]
    assert binding.kind == "local_borrow"
    assert binding.operands[:2] == ("r", "Box")
    assert binding.operands[2].kind == "var"
    assert binding.operands[2].operands == ("x",)
    assert binding.operands[2].binding_id == program.functions[0].body[0].binding_id
    assert binding.binding_id.name == "r"
    Checker(program).check()


@pytest.mark.parametrize("gap", [" ", "\n"])
def test_local_borrow_whitespace(gap: str) -> None:
    source = (
        "module m\nfn main()->i32 { let x:i32=1; "
        f"let r: borrow{gap}i32 = borrow{gap}x; return x; }}"
    )
    assert parse(source).functions[0].body[1].kind == "local_borrow"


def test_local_borrow_accepts_line_comments_between_tokens() -> None:
    source = (
        "module m\nfn main()->i32 { let x:i32=1;\n"
        "let r: borrow // type follows\n i32 = borrow // origin follows\n x;\n"
        "return x; }"
    )
    assert parse(source).functions[0].body[1].kind == "local_borrow"


def test_existing_borrow_identifiers_and_parameter_are_unchanged() -> None:
    source = (
        "module m\n"
        "struct borrow { value:i32; }\n"
        "fn view(borrow x:borrow)->i32 { return x.value; }\n"
        "fn main()->i32 { let borrow:i32=1; "
        "let x:borrow=borrow {value:borrow}; return view(x); }"
    )
    program = parse(source)
    Checker(program).check()
    assert program.functions[1].body[0].kind == "let"
    assert program.functions[1].body[1].kind == "let"
