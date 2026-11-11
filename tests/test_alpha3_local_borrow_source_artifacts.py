"""Source-backed RM1 representation evidence for the bounded oracle producer."""

import pytest

from merit.bootstrap.hir_contract import canonical_hir_json, load_hir_json
from merit.bootstrap.hir_to_mir import lower_hir_to_mir
from merit.bootstrap.local_borrow_source_hir import (
    LocalBorrowSourceHirError, lower_checked_local_borrow_source_hir,
)
from merit.bootstrap.mir_contract import canonical_mir_json, load_mir_json
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


def test_accepted_but_unrepresented_source_fails_closed() -> None:
    source = SOURCE.replace("inspect(r);", "print(r);")
    with pytest.raises(LocalBorrowSourceHirError, match="unsupported RM1 source statement"):
        lower_checked_local_borrow_source_hir(source)


def test_other_numeric_type_cannot_be_mislabeled_as_i32() -> None:
    source = SOURCE.replace("let x:i32=1; let r: borrow i32=borrow x;",
                            "let x:i64=1; let r: borrow i64=borrow x;")
    source = source.replace("inspect(r);", "return 0;").replace("return 0; return x;", "return 0;")
    with pytest.raises(LocalBorrowSourceHirError, match="unsupported RM1 source binding type"):
        lower_checked_local_borrow_source_hir(source)
