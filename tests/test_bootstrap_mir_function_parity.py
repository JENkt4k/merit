from __future__ import annotations

import pytest

from merit.bootstrap.hir_contract import HirBinding, HirModule, HirNode, HirType, SourceSpan
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.mir_contract import canonical_mir_json
from merit.bootstrap.mir_function_parity import (
    NativeMirFunctionError,
    lower_native_function_mir_records,
)


SOURCE = "module demo\nfn compute()->i64 { let x:i64=1+2; var y:i64=x*3; return y+4; }\n"
I64 = HirType("i64")


def native_records():
    # kind,start,length,id,result,left,right,symbol_start,symbol_length,symbol_code,
    # type_code,numeric_policy,binding_id,mutable,hir_node_id,ordinal
    return [
        (1, 12, 63, 0, -1, -1, -1, 15, 7, 0, 1, 0, -1, 0, -1, 0),
        (2, 36, 1, 0, -1, -1, -1, 36, 1, 0, 1, 0, 0, 0, -1, 0),
        (2, 51, 1, 1, -1, -1, -1, 51, 1, 0, 1, 0, 1, 1, -1, 1),
        (3, 0, 0, 2, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 2, 2),
        (3, 0, 0, 3, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 0, 3),
        (3, 0, 0, 4, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 1, 4),
        (4, 42, 1, 0, 3, -1, -1, -1, 0, 0, 1, 0, -1, 0, 0, 0),
        (4, 44, 1, 1, 4, -1, -1, -1, 0, 0, 1, 0, -1, 0, 1, 1),
        (5, 42, 3, 2, 2, 3, 4, -1, 0, 1, 1, 2, -1, 0, 2, 2),
        (6, 32, 14, 3, 0, 2, -1, -1, 0, 0, 0, 0, 0, 0, 3, 3),
        (3, 0, 0, 5, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 6, 5),
        (3, 0, 0, 6, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 5, 6),
        (4, 59, 1, 4, 6, -1, -1, -1, 0, 0, 1, 0, -1, 0, 5, 4),
        (5, 57, 3, 5, 5, 0, 6, -1, 0, 3, 1, 2, -1, 0, 6, 5),
        (6, 47, 14, 6, 1, 5, -1, -1, 0, 0, 0, 0, 1, 0, 7, 6),
        (3, 0, 0, 7, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 10, 7),
        (3, 0, 0, 8, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 9, 8),
        (4, 71, 1, 7, 8, -1, -1, -1, 0, 0, 1, 0, -1, 0, 9, 7),
        (5, 69, 3, 8, 7, 1, 8, -1, 0, 1, 1, 2, -1, 0, 10, 8),
        (7, 62, 11, 0, -1, 7, -1, -1, 0, 0, 0, 0, -1, 0, 11, 0),
    ]


def reference_hir():
    bindings = (
        HirBinding(0, "x", I64),
        HirBinding(1, "y", I64, mutable=True),
    )
    nodes = (
        HirNode(0, "literal", I64, span=SourceSpan(42, 1), value="1", numeric_policy="exact"),
        HirNode(1, "literal", I64, span=SourceSpan(44, 1), value="2", numeric_policy="exact"),
        HirNode(2, "binary", I64, children=(0, 1), span=SourceSpan(42, 3), symbol="+", numeric_policy="checked"),
        HirNode(3, "let", I64, children=(2,), span=SourceSpan(32, 14), binding_id=0),
        HirNode(4, "identifier", I64, span=SourceSpan(57, 1), binding_id=0, ownership="value"),
        HirNode(5, "literal", I64, span=SourceSpan(59, 1), value="3", numeric_policy="exact"),
        HirNode(6, "binary", I64, children=(4, 5), span=SourceSpan(57, 3), symbol="*", numeric_policy="checked"),
        HirNode(7, "let", I64, children=(6,), span=SourceSpan(47, 14), binding_id=1),
        HirNode(8, "identifier", I64, span=SourceSpan(69, 1), binding_id=1, ownership="value"),
        HirNode(9, "literal", I64, span=SourceSpan(71, 1), value="4", numeric_policy="exact"),
        HirNode(10, "binary", I64, children=(8, 9), span=SourceSpan(69, 3), symbol="+", numeric_policy="checked"),
        HirNode(11, "return", I64, children=(10,), span=SourceSpan(62, 11)),
        HirNode(12, "function", I64, children=(3, 7, 11), symbol="compute"),
    )
    return HirModule("demo", bindings, nodes, (12,))


def test_native_straight_line_function_records_match_canonical_hir_to_mir():
    reference = lower_hir_to_mir(reference_hir())
    native = lower_native_function_mir_records(native_records(), SOURCE, module_name="demo")
    assert canonical_mir_json(native) == canonical_mir_json(reference)


def test_function_record_contract_preserves_binding_mutability_and_hir_temp_identity():
    native = lower_native_function_mir_records(native_records(), SOURCE, module_name="demo")
    function = native.functions[0]
    assert [(local.local_id, local.name, local.mutable, local.source_binding_id) for local in function.locals[:2]] == [
        (0, "x", False, 0),
        (1, "y", True, 1),
    ]
    assert [local.name for local in function.locals[2:]] == [
        "_t2", "_t0", "_t1", "_t6", "_t5", "_t10", "_t9"
    ]
    assert [instruction.kind for instruction in function.blocks[0].instructions] == [
        "const", "const", "binary", "copy", "const", "binary", "copy", "const", "binary"
    ]
    assert function.blocks[0].terminator.operands == (7,)


@pytest.mark.parametrize(
    "record_index,field_index,value,message",
    [
        (1, 3, 1, "source local IDs must be dense"),
        (2, 13, 2, "invalid mutability"),
        (3, 14, -1, "invalid HIR identity"),
        (8, 11, 1, "arithmetic binary"),
        (9, 12, 1, "destination does not match binding"),
        (19, 5, 99, "unknown local"),
    ],
)
def test_malformed_native_function_records_are_rejected(record_index, field_index, value, message):
    records = [list(record) for record in native_records()]
    records[record_index][field_index] = value
    with pytest.raises(NativeMirFunctionError, match=message):
        lower_native_function_mir_records(records, SOURCE, module_name="demo")
