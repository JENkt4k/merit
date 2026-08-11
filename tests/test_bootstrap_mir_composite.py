from __future__ import annotations

import pytest

from merit.bootstrap.hir_contract import HirModule, HirNode, HirType, SourceSpan
from merit.bootstrap.mir_composite_parity import (
    NativeMirCompositeError,
    lower_native_composite_mir_records,
)
from merit.bootstrap.mir_contract import MirType
from merit.bootstrap.mir_expression import lower_expression_hir_to_mir


I64 = HirType("i64")
ACCOUNT = HirType("Account")


def test_reference_field_lowering_emits_load_field():
    hir = HirModule(
        "field",
        (),
        (
            HirNode(0, "literal", ACCOUNT, span=SourceSpan(0, 1), value="a"),
            HirNode(
                1,
                "field",
                I64,
                children=(0,),
                span=SourceSpan(0, 9),
                symbol="balance",
                ownership="value",
            ),
        ),
        (1,),
    )
    function = lower_expression_hir_to_mir(hir).functions[0]
    assert [instruction.kind for instruction in function.blocks[0].instructions] == [
        "const",
        "load_field",
    ]
    assert function.blocks[0].instructions[1].symbol == "balance"
    assert function.blocks[0].instructions[1].operands == (1,)


def test_native_empty_call_preserves_resolved_symbol():
    native = lower_native_composite_mir_records(
        [(4, 0, 3, 0, -1, -1, 0, 1, 0, 1, 0, -1, 0, -1, -1)],
        "f()",
        module_name="empty-call",
    )
    instruction = native.functions[0].blocks[0].instructions[0]
    assert instruction.kind == "call"
    assert instruction.symbol == "f"
    assert instruction.operands == ()


def test_native_ordered_call_operands_are_dense_and_stable():
    records = [
        (1, 2, 1, 1, -1, -1, -1, 0, 0, 1, 0, -1, 0, -1, -1),
        (1, 4, 1, 2, -1, -1, -1, 0, 0, 1, 0, -1, 1, -1, -1),
        (7, 0, 0, 1, -1, -1, -1, 0, 0, 0, 0, -1, -1, 2, 0),
        (7, 0, 0, 2, -1, -1, -1, 0, 0, 0, 0, -1, -1, 2, 1),
        (4, 0, 6, 0, -1, -1, 0, 1, 0, 1, 0, -1, 2, -1, -1),
    ]
    native = lower_native_composite_mir_records(
        records,
        "f(1,2)",
        module_name="ordered-call",
    )
    call = native.functions[0].blocks[0].instructions[-1]
    assert call.kind == "call"
    assert call.operands == (1, 2)


def test_native_field_uses_explicit_receiver_and_symbol_span():
    native = lower_native_composite_mir_records(
        [
            (3, 0, 7, 0, -1, -1, -1, 0, 0, 3, 0, 0, 0, -1, -1),
            (5, 0, 15, 1, 0, -1, 8, 7, 0, 1, 0, -1, 1, -1, -1),
        ],
        "account.balance",
        module_name="field",
        type_names={3: MirType("Account")},
    )
    field = native.functions[0].blocks[0].instructions[0]
    assert field.kind == "load_field"
    assert field.symbol == "balance"
    assert field.operands == (0,)


@pytest.mark.parametrize(
    "records,message",
    [
        ([], "empty"),
        ([(7, 0, 0, 9, -1, -1, -1, 0, 0, 0, 0, -1, -1, 0, 0)], "unknown local"),
        (
            [
                (1, 2, 1, 1, -1, -1, -1, 0, 0, 1, 0, -1, 0, -1, -1),
                (7, 0, 0, 1, -1, -1, -1, 0, 0, 0, 0, -1, -1, 2, 1),
                (4, 0, 4, 0, -1, -1, 0, 1, 0, 1, 0, -1, 2, -1, -1),
            ],
            "non-dense",
        ),
        ([(4, 0, 3, 0, -1, -1, -1, 0, 0, 1, 0, -1, 0, -1, -1)], "symbol span"),
        ([(1, 0, 1, 0, -1, -1, -1, 0, 0, 9, 0, -1, 0, -1, -1)], "type code"),
    ],
)
def test_malformed_composite_mir_is_rejected(records, message):
    with pytest.raises(NativeMirCompositeError, match=message):
        lower_native_composite_mir_records(records, "f(1)", module_name="bad")
