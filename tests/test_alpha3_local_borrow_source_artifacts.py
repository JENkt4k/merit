"""Source-backed RM1 representation evidence for the bounded oracle producer."""

from dataclasses import replace

import pytest

from merit.bootstrap.hir_contract import canonical_hir_json, load_hir_json
from merit.bootstrap.hir_to_mir import HirToMirError, lower_hir_to_mir
from merit.bootstrap.local_borrow_source_hir import (
    LocalBorrowSourceHirError, lower_checked_local_borrow_source_hir,
)
from merit.bootstrap.mir_contract import canonical_mir_json, load_mir_json
from merit.bootstrap.resolved_source_function_bundle import (
    LOCAL_LOAN_PROJECT_ARTIFACT_BUNDLE_VERSION,
    decode_native_project_artifact_transport,
    decode_resolved_source_function_bundle,
    encode_resolved_source_function_bundle,
)
from merit.compiler import CompileError


SOURCE = (
    "module rm1\n"
    "fn inspect(borrow value:i32)->i32 { return value; }\n"
    "fn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; inspect(r); return x; }"
)


def test_checked_source_produces_ordered_v2_create_use_end() -> None:
    hir = lower_checked_local_borrow_source_hir(SOURCE)
    assert hir.schema == "bootstrap-hir-v2"
    assert [(loan.reference_binding_id, loan.origin_binding_id) for loan in hir.local_loans] == [(3, 2)]
    assert SOURCE[hir.local_loans[0].span.start:][:hir.local_loans[0].span.length].startswith(
        "let r: borrow i32=borrow x"
    )
    mir = lower_hir_to_mir(hir)
    assert mir.schema == "bootstrap-mir-v2"
    assert [effect.kind for effect in mir.functions[0].local_loan_effects] == ["create", "use", "end"]
    assert [effect.instruction_id for effect in mir.functions[0].local_loan_effects] == [2, 3, 3]
    assert load_hir_json(canonical_hir_json(hir)) == hir
    assert load_mir_json(canonical_mir_json(mir)) == mir
    assert canonical_hir_json(lower_checked_local_borrow_source_hir(SOURCE)) == canonical_hir_json(hir)


def test_rejected_source_never_produces_v2_artifacts() -> None:
    invalid = SOURCE.replace("inspect(r); return x;", "x=2; inspect(r); return x;")
    with pytest.raises(CompileError, match="M5402"):
        lower_checked_local_borrow_source_hir(invalid)


def test_source_final_use_precedes_owner_assignment_in_mir() -> None:
    source = SOURCE.replace("let x:i32=1;", "var x:i32=1;").replace(
        "inspect(r); return x;", "inspect(r); x=2; return x;"
    )
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    instructions = mir.functions[0].blocks[0].instructions
    end = next(effect for effect in mir.functions[0].local_loan_effects if effect.kind == "end")
    assignment = next(instruction for instruction in instructions
                      if instruction.kind == "copy" and instruction.result == 0
                      and instruction.instruction_id > end.instruction_id)
    assert end.instruction_id < assignment.instruction_id
    with pytest.raises(CompileError, match="M5402"):
        lower_checked_local_borrow_source_hir(source.replace("inspect(r); x=2;", "x=2; inspect(r);"))


def test_two_shared_loans_end_independently_before_owner_assignment() -> None:
    source = SOURCE.replace("let x:i32=1;", "var x:i32=1;").replace(
        "inspect(r); return x;",
        "let s: borrow i32=borrow x; inspect(r); inspect(s); x=2; return x;",
    )
    hir = lower_checked_local_borrow_source_hir(source)
    assert len(hir.local_loans) == 2
    mir = lower_hir_to_mir(hir)
    effects = mir.functions[0].local_loan_effects
    assert [effect.kind for effect in effects] == ["create", "create", "use", "end", "use", "end"]
    assert effects[-1].instruction_id < next(
        instruction.instruction_id for instruction in mir.functions[0].blocks[0].instructions
        if instruction.kind == "copy" and instruction.result == 0
        and instruction.instruction_id > effects[-1].instruction_id
    )
    assert load_mir_json(canonical_mir_json(mir)) == mir


def test_owned_string_waits_for_correct_move_and_cleanup_lowering() -> None:
    source = (
        'module rm1\n'
        'fn inspect(borrow value:String)->i32 { print(value); return 0; }\n'
        'fn main()->i32 { let x:String="a"; let r: borrow String=borrow x; '
        'inspect(r); drop(x); return 0; }'
    )
    with pytest.raises(LocalBorrowSourceHirError, match="unsupported RM1 source binding type"):
        lower_checked_local_borrow_source_hir(source)


def test_v2_bridge_rejects_unproven_owned_initializer() -> None:
    hir = lower_checked_local_borrow_source_hir(SOURCE)
    owner = next(binding for binding in hir.bindings if binding.name == "x")
    changed = replace(hir, bindings=tuple(
        replace(binding, ownership="owned") if binding == owner else binding
        for binding in hir.bindings
    ))
    with pytest.raises(HirToMirError, match="owned initializer requires proven move"):
        lower_hir_to_mir(changed)


def test_checked_source_mir_v2_survives_v5_transport() -> None:
    mir_bytes = canonical_mir_json(lower_hir_to_mir(
        lower_checked_local_borrow_source_hir(SOURCE)
    )).encode("utf-8")
    transport = encode_resolved_source_function_bundle(
        (), module_name="rm1", canonical_mir=mir_bytes,
        c_source=b"/* transport fixture only */", c_header=b"/* transport fixture only */",
        project_artifact_version=LOCAL_LOAN_PROJECT_ARTIFACT_BUNDLE_VERSION,
    )
    decoded = decode_resolved_source_function_bundle(transport)
    assert decode_native_project_artifact_transport(transport).version == LOCAL_LOAN_PROJECT_ARTIFACT_BUNDLE_VERSION
    assert decoded.canonical_mir_bytes == mir_bytes


def test_accepted_but_unrepresented_source_fails_closed() -> None:
    source = SOURCE.replace("inspect(r);", "let y:i32=1+2; inspect(r);")
    with pytest.raises(LocalBorrowSourceHirError, match="unsupported RM1 source expression"):
        lower_checked_local_borrow_source_hir(source)


def test_actual_final_read_and_post_use_assignment_lower_from_source() -> None:
    source = SOURCE.replace("let x:i32=1;", "var x:i32=1;").replace(
        "inspect(r); return x;", "print(r); x=2; return x;"
    )
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    instructions = mir.functions[0].blocks[0].instructions
    read = next(instruction for instruction in instructions if instruction.kind == "print")
    end = next(effect for effect in mir.functions[0].local_loan_effects if effect.kind == "end")
    assert read.instruction_id == end.instruction_id
    assert any(instruction.kind == "copy" and instruction.result == 0
               and instruction.instruction_id > end.instruction_id for instruction in instructions)


def test_actual_case_24_call_then_print_has_two_ordered_uses() -> None:
    source = SOURCE.replace("inspect(r); return x;", "inspect(r); print(r); return x;")
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    effects = mir.functions[0].local_loan_effects
    assert [effect.kind for effect in effects] == ["create", "use", "use", "end"]
    assert effects[-1].instruction_id == next(
        instruction.instruction_id for instruction in mir.functions[0].blocks[0].instructions
        if instruction.kind == "print"
    )


def test_other_numeric_type_cannot_be_mislabeled_as_i32() -> None:
    source = SOURCE.replace("let x:i32=1; let r: borrow i32=borrow x;",
                            "let x:i64=1; let r: borrow i64=borrow x;")
    source = source.replace("inspect(r);", "return 0;").replace("return 0; return x;", "return 0;")
    with pytest.raises(LocalBorrowSourceHirError, match="unsupported RM1 source binding type"):
        lower_checked_local_borrow_source_hir(source)
