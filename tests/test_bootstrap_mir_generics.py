import pytest

from merit.bootstrap.hir_contract import HirModule, HirNode, HirType, SourceSpan as HirSpan
from merit.bootstrap.mir_contract import MirContractError, MirInstruction, MirType, canonical_mir_json, load_mir_json
from merit.bootstrap.mir_expression import lower_expression_hir_to_mir
from merit.bootstrap.mir_generic_parity import (
    NativeMirGenericError,
    generic_mir_parity_observations,
    lower_native_generic_mir_records,
)


I64_HIR = HirType("i64")
I64_MIR = MirType("i64")
SOURCE = "identity<i64>(1)"


def generic_hir() -> HirModule:
    literal = HirNode(
        0, "literal", I64_HIR, span=HirSpan(14, 1), value="1",
        ownership="value", numeric_policy="checked",
    )
    call = HirNode(
        1, "call", I64_HIR, children=(0,), span=HirSpan(0, len(SOURCE)),
        symbol="identity", ownership="value", generic_arguments=(I64_HIR,),
    )
    return HirModule("single-generic-call", (), (literal, call), (1,))


def native_records():
    return (
        (1, 14, 1, 1, -1, -1, 0, 1, 0, 0, -1, -1),
        (3, 0, 0, 1, -1, -1, 0, 0, 0, -1, 1, 0),
        (2, 0, len(SOURCE), 0, -1, 0, 8, 1, 1, 1, -1, -1),
    )


def test_mir_call_specialization_is_first_class_and_round_trips():
    mir = lower_expression_hir_to_mir(generic_hir())
    call = mir.functions[0].blocks[0].instructions[-1]
    assert call.kind == "call"
    assert call.symbol == "identity"
    assert call.specialization == (I64_MIR,)
    encoded = canonical_mir_json(mir)
    assert '"specialization":[{"name":"i64"}]' in encoded
    assert load_mir_json(encoded) == mir


def test_specialization_is_rejected_on_non_call_instruction():
    with pytest.raises(MirContractError, match="only valid on call"):
        MirInstruction(0, "const", specialization=(I64_MIR,))


def test_native_generic_records_match_reference_mir_without_source_relowering():
    reference, bootstrap = generic_mir_parity_observations(
        "single-generic-call",
        generic_hir(),
        native_records(),
        SOURCE,
        type_names={1: I64_MIR},
    )
    assert reference.digest == bootstrap.digest


def test_native_generic_record_requires_explicit_specialization_identity():
    broken = list(native_records())
    call = list(broken[-1])
    call[8] = 0
    broken[-1] = tuple(call)
    with pytest.raises(NativeMirGenericError, match="lacks specialization identity"):
        lower_native_generic_mir_records(
            broken, SOURCE, module_name="single-generic-call", type_names={1: I64_MIR}
        )


def test_native_generic_operands_must_be_dense_and_known():
    broken = list(native_records())
    marker = list(broken[1])
    marker[11] = 1
    broken[1] = tuple(marker)
    with pytest.raises(NativeMirGenericError, match="non-dense operand ordinals"):
        lower_native_generic_mir_records(
            broken, SOURCE, module_name="single-generic-call", type_names={1: I64_MIR}
        )
