from __future__ import annotations

import pytest

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType, SourceSpan
from merit.bootstrap.mir_contract import MirType, canonical_mir_json
from merit.bootstrap.mir_expression import ExpressionMirLoweringError, lower_expression_hir_to_mir
from merit.bootstrap.mir_parity import NativeMirExpressionError, lower_native_expression_mir_records


I64 = HirType("i64")
BOOL = HirType("bool")


def _hir(nodes, *, bindings=(), root=None, name="expr"):
    if root is None:
        root = nodes[-1].node_id
    return HirModule(name, tuple(bindings), tuple(nodes), (root,))


def test_expression_bridge_wraps_checked_value_in_returning_function():
    hir = _hir(
        [
            HirNode(0, "literal", I64, value="1", span=SourceSpan(0, 1)),
            HirNode(1, "literal", I64, value="2", span=SourceSpan(2, 1)),
            HirNode(
                2,
                "binary",
                I64,
                children=(0, 1),
                span=SourceSpan(0, 3),
                symbol="+",
                numeric_policy="checked",
            ),
        ]
    )
    function = lower_expression_hir_to_mir(hir).functions[0]
    assert function.name == "expr"
    assert [local.name for local in function.locals] == ["_t2", "_t0", "_t1"]
    assert [instruction.kind for instruction in function.blocks[0].instructions] == [
        "const",
        "const",
        "binary",
    ]
    assert function.blocks[0].terminator.operands == (0,)


def test_native_arithmetic_records_match_reference_mir_exactly():
    source = "1+2"
    reference = lower_expression_hir_to_mir(
        _hir(
            [
                HirNode(0, "literal", I64, value="1", span=SourceSpan(0, 1)),
                HirNode(1, "literal", I64, value="2", span=SourceSpan(2, 1)),
                HirNode(
                    2,
                    "binary",
                    I64,
                    children=(0, 1),
                    span=SourceSpan(0, 3),
                    symbol="+",
                    numeric_policy="checked",
                ),
            ]
        )
    )
    native = lower_native_expression_mir_records(
        [
            (1, 0, 1, 1, -1, -1, 0, 1, 0, -1, 0),
            (1, 2, 1, 2, -1, -1, 0, 1, 0, -1, 1),
            (2, 0, 3, 0, 1, 2, 1, 1, 2, -1, 2),
        ],
        source,
        module_name="expr",
    )
    assert canonical_mir_json(native) == canonical_mir_json(reference)


def test_native_binding_and_comparison_records_preserve_source_local_identity():
    source = "a==b"
    reference = lower_expression_hir_to_mir(
        _hir(
            [
                HirNode(0, "identifier", I64, binding_id=0, span=SourceSpan(0, 1)),
                HirNode(1, "identifier", I64, binding_id=1, span=SourceSpan(3, 1)),
                HirNode(
                    2,
                    "binary",
                    BOOL,
                    children=(0, 1),
                    span=SourceSpan(0, 4),
                    symbol="==",
                    numeric_policy="exact",
                ),
            ],
            bindings=(HirBinding(0, "a", I64), HirBinding(1, "b", I64)),
        )
    )
    native = lower_native_expression_mir_records(
        [
            (4, 0, 1, 0, -1, -1, 0, 1, 0, 0, 0),
            (4, 3, 1, 1, -1, -1, 0, 1, 0, 1, 1),
            (2, 0, 4, 2, 0, 1, 5, 2, 1, -1, 2),
        ],
        source,
        module_name="expr",
    )
    assert canonical_mir_json(native) == canonical_mir_json(reference)
    assert [local.source_binding_id for local in native.functions[0].locals] == [0, 1, None]


def test_native_group_alias_does_not_allocate_or_emit_instruction():
    native = lower_native_expression_mir_records(
        [
            (1, 1, 1, 0, -1, -1, 0, 1, 0, -1, 0),
            (3, 0, 3, 0, 0, -1, 0, 1, 0, -1, 0),
        ],
        "(1)",
        module_name="group",
    )
    function = native.functions[0]
    assert len(function.locals) == 1
    assert len(function.blocks[0].instructions) == 1
    assert function.blocks[0].terminator.operands == (0,)


def test_expression_bridge_rejects_multiple_roots():
    hir = HirModule(
        "bad",
        (),
        (
            HirNode(0, "literal", I64, value="1"),
            HirNode(1, "literal", I64, value="2"),
        ),
        (0, 1),
    )
    with pytest.raises(ExpressionMirLoweringError, match="exactly one"):
        lower_expression_hir_to_mir(hir)


@pytest.mark.parametrize(
    "records,message",
    [
        ([], "empty"),
        ([(1, 0, 1, 0, -1, -1, 0, 9, 0, -1, 0)], "type code"),
        ([(2, 0, 3, 0, 4, 5, 1, 1, 2, -1, 0)], "unknown operand"),
        ([(1, 0, 1, 1, -1, -1, 0, 1, 0, -1, 0)], "densely"),
        ([(4, 0, 1, 1, -1, -1, 0, 1, 0, 1, 0)], "dense"),
    ],
)
def test_malformed_native_expression_mir_is_rejected(records, message):
    with pytest.raises(NativeMirExpressionError, match=message):
        lower_native_expression_mir_records(records, "a+1", module_name="bad")


def test_custom_type_code_must_be_explicit():
    native = lower_native_expression_mir_records(
        [(1, 0, 3, 0, -1, -1, 0, 7, 0, -1, 0)],
        "123",
        module_name="typed",
        type_names={7: MirType("Count")},
    )
    assert native.functions[0].locals[0].type == MirType("Count")
