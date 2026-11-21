"""Bounded RM2 checker cases for one immutable loan across an if join."""

import pytest

from merit.compiler import Checker, CompileError, parse


def check(body: str, *, declarations: str = "", functions: str = "") -> None:
    program = parse(
        f"module rm2\n{declarations}\n{functions}\n"
        f"fn main()->i32 {{ {body} return 0; }}"
    )
    Checker(program).check()


@pytest.mark.parametrize("condition", [0, 1])
def test_one_arm_read_ends_at_join_before_owner_write(condition: int) -> None:
    check(
        f"var x:i32=1; let r: borrow i32 = borrow x; "
        f"if {condition} {{ print(r); }} x=2; print(x);"
    )


def test_both_arms_read_before_one_owner_drop() -> None:
    check(
        "let x:Box=Box {value:1}; let r: borrow Box = borrow x; "
        "if 1 { print(r.value); } else { print(r.value); } drop(x);",
        declarations="struct Box { value:i32; } destructor Box { print(9); }",
    )


def test_proven_borrowed_call_in_one_arm() -> None:
    check(
        "var x:i32=1; let r: borrow i32 = borrow x; "
        "if 1 { inspect(r); } else { print(0); } x=2;",
        functions="fn inspect(borrow value:i32)->i32 { return value; }",
    )


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("if 1 { x=2; } print(r);", "M5402"),
        ("if 1 { drop(x); } print(r);", "M5402"),
        ("if 1 { print(r); x=2; }", "M5402"),
        ("if 1 { print(r); } else { x=2; }", "M5402"),
        ("if 1 { return r; } print(r);", "M5403"),
        ("if 1 { unknown(r); } print(r);", "M3004"),
        ("if 1 { print(r); } while 1 { print(r); }", "M5403"),
        ("if 1 { if 1 { print(r); } } print(r);", "M5403"),
    ],
)
def test_conflicts_and_unsupported_flow_fail_closed(body: str, code: str) -> None:
    with pytest.raises(CompileError, match=code):
        check("var x:i32=1; let r: borrow i32 = borrow x; " + body)


def test_branch_conflict_retains_creation_note() -> None:
    source=("module rm2\nfn main()->i32 { var x:i32=1; "
            "let r: borrow i32 = borrow x; if 1 { x=2; } "
            "print(r); return 0; }")
    with pytest.raises(CompileError) as caught:
        Checker(parse(source)).check()
    assert caught.value.code == "M5402"
    assert caught.value.span is not None
    assert any("created" in note.message and note.span is not None
               for note in caught.value.notes)
