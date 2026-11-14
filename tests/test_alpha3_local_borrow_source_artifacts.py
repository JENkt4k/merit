"""Source-backed RM1 representation evidence for the bounded oracle producer."""

from dataclasses import replace

import pytest

from merit.bootstrap.hir_contract import canonical_hir_json, load_hir_json
from merit.bootstrap.hir_to_mir import HirToMirError, lower_hir_to_mir
from merit.bootstrap.local_borrow_source_hir import (
    LocalBorrowSourceHirError, lower_checked_local_borrow_source_hir,
)
from merit.bootstrap.mir_contract import MirContractError, canonical_mir_json, load_mir_json
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


def test_owned_string_moves_into_owner_and_drops_after_loan_end() -> None:
    source = (
        'module rm1\n'
        'fn inspect(borrow value:String)->i32 { print(value); return 0; }\n'
        'fn main()->i32 { let x:String="a"; let r: borrow String=borrow x; '
        'inspect(r); drop(x); return 0; }'
    )
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    function = mir.functions[0]
    assert function.locals[0].ownership == "owned"
    assert function.locals[1].ownership == "local_reference"
    instructions = function.blocks[0].instructions
    assert any(instruction.kind == "move" and instruction.result == 0 for instruction in instructions)
    end = next(effect.instruction_id for effect in function.local_loan_effects if effect.kind == "end")
    drops = [instruction for instruction in instructions if instruction.kind == "drop"]
    assert len(drops) == 1 and drops[0].operands == (0,) and end < drops[0].instruction_id


def test_case_01_implicit_string_cleanup_and_case_02_shared_loans() -> None:
    source = ('module rm1\nfn main()->i32 { let x:String="a"; '
              'let r: borrow String=borrow x; print(r); return 0; }')
    single = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    single_function = single.functions[0]
    assert [instruction.kind for instruction in single_function.blocks[0].instructions].count("drop") == 1
    assert single_function.blocks[0].instructions[-1].kind == "drop"
    shared = source.replace('print(r);', 'let s: borrow String=borrow x; print(r); print(s);')
    dual = lower_hir_to_mir(lower_checked_local_borrow_source_hir(shared))
    effects = dual.functions[0].local_loan_effects
    assert [effect.kind for effect in effects] == ["create", "create", "use", "end", "use", "end"]
    assert effects[-1].instruction_id < dual.functions[0].blocks[0].instructions[-1].instruction_id


@pytest.mark.parametrize(("mutation", "message"), [
    ("omit_drop", "without cleanup or transfer"),
    ("duplicate_drop", "used after move or drop"),
    ("use_after_drop", "used after move or drop"),
])
def test_v2_reader_rejects_invalid_owned_cleanup(mutation, message) -> None:
    source = ('module rm1\nfn main()->i32 { let x:String="a"; '
              'let r: borrow String=borrow x; print(r); return 0; }')
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    function = mir.functions[0]
    block = function.blocks[0]
    instructions = list(block.instructions)
    drop = instructions[-1]
    if mutation == "omit_drop":
        instructions.pop()
    elif mutation == "duplicate_drop":
        instructions.append(replace(drop, instruction_id=drop.instruction_id + 1))
    else:
        instructions.append(replace(drop, instruction_id=drop.instruction_id + 1,
                                    kind="print", ownership="none"))
    with pytest.raises(MirContractError, match=message):
        replace(function, blocks=(replace(block, instructions=tuple(instructions)),))


def test_case_08_owner_drop_before_final_read_emits_no_artifact() -> None:
    source = ('module rm1\nfn main()->i32 { let x:String="a"; '
              'let r: borrow String=borrow x; drop(x); print(r); return 0; }')
    with pytest.raises(CompileError, match="M5402"):
        lower_checked_local_borrow_source_hir(source)


def test_case_07_aggregate_owner_moves_after_field_read() -> None:
    source = (
        "module rm1\nstruct Box { value:i32; }\n"
        "fn main()->i32 { let x:Box=Box{value:1}; "
        "let r: borrow Box=borrow x; print(r.value); "
        "let y:Box=x; print(y.value); return 0; }"
    )
    hir = lower_checked_local_borrow_source_hir(source)
    mir = lower_hir_to_mir(hir)
    function = mir.functions[0]
    instructions = function.blocks[0].instructions
    end = next(effect.instruction_id for effect in function.local_loan_effects if effect.kind == "end")
    assert instructions[end].kind == "load_field"
    owner_moves = [instruction for instruction in instructions if instruction.kind == "move"]
    assert len(owner_moves) == 2
    assert owner_moves[1].operands == (0,) and owner_moves[1].instruction_id > end
    drops = [instruction for instruction in instructions if instruction.kind == "drop"]
    assert len(drops) == 1 and drops[0].operands == (2,)
    assert load_mir_json(canonical_mir_json(mir)) == mir


@pytest.mark.parametrize(("order", "message"), [
    ((0, 3, 1, 2, 4, 5), "origin is no longer owned and valid"),
    ((0, 1, 3, 2, 4, 5), "owner resource invalidated while local loan is live"),
])
def test_v2_bridge_rejects_aggregate_move_before_loan_end(order, message) -> None:
    source = (
        "module rm1\nstruct Box { value:i32; }\n"
        "fn main()->i32 { let x:Box=Box{value:1}; let r: borrow Box=borrow x; "
        "print(r.value); let y:Box=x; print(y.value); return 0; }"
    )
    hir = lower_checked_local_borrow_source_hir(source)
    function = hir.nodes[hir.roots[0]]
    children = tuple(function.children[index] for index in order)
    changed = replace(hir, nodes=tuple(
        replace(node, children=children) if node.node_id == function.node_id else node
        for node in hir.nodes
    ))
    with pytest.raises((HirToMirError, ValueError), match=message):
        lower_hir_to_mir(changed)


@pytest.mark.parametrize(("case", "declarations", "body", "diagnostic"), [
    ("05", "", "var x:i32=1; let r: borrow i32=borrow x; x=2; print(r);", "M5402"),
    ("06", "struct Box { value:i32; }", "let x:Box=Box{value:1}; let r: borrow Box=borrow x; let y:Box=x; print(r.value);", "M5402"),
    ("08", "", 'let x:String="a"; let r: borrow String=borrow x; drop(x); print(r);', "M5402"),
    ("22", "", "let x:i32=1; let r: borrow i32=borrow x; return r;", "M5404"),
    ("23", "struct Holder { value:i32; }", "let x:i32=1; let r: borrow i32=borrow x; let h:Holder=Holder{value:r};", "M5404"),
    ("28", "", 'let x:String="a"; let r: borrow String=borrow x; replace(x,"b"); print(r);', "M5402"),
])
def test_required_rejections_stop_before_source_artifacts(case, declarations, body, diagnostic) -> None:
    source = f"module rm1\n{declarations}\nfn main()->i32 {{ {body} return 0; }}"
    with pytest.raises(CompileError, match=diagnostic):
        lower_checked_local_borrow_source_hir(source)


@pytest.mark.parametrize(("kind", "message"), [
    ("move", "owned move requires cleanup proof"),
    ("call", "owned call requires transfer proof"),
])
def test_v2_bridge_rejects_unproven_owned_use(kind, message) -> None:
    source = ('module rm1\nfn main()->i32 { let x:String="a"; '
              'let r: borrow String=borrow x; print(r); return 0; }')
    hir = lower_checked_local_borrow_source_hir(source)
    owner = next(binding for binding in hir.bindings if binding.name == "x")
    origin = next(node for node in hir.nodes if node.kind == "identifier" and node.binding_id == owner.binding_id)
    nodes = tuple(
        replace(node, kind=kind, children=(origin.node_id,),
                type=owner.type if kind == "move" else node.type,
                binding_id=owner.binding_id if kind == "move" else None,
                symbol="consume" if kind == "call" else None)
        if node.kind == "print" else node for node in hir.nodes
    )
    with pytest.raises(HirToMirError, match=message):
        lower_hir_to_mir(replace(hir, nodes=nodes))


def test_v2_bridge_rejects_duplicate_owned_drop() -> None:
    source = ('module rm1\nfn main()->i32 { let x:String="a"; '
              'let r: borrow String=borrow x; print(r); drop(x); return 0; }')
    hir = lower_checked_local_borrow_source_hir(source)
    owner = next(binding for binding in hir.bindings if binding.name == "x")
    nodes = tuple(
        replace(node, kind="drop", type=owner.type, children=(), binding_id=owner.binding_id)
        if node.kind == "return" else node for node in hir.nodes
    )
    with pytest.raises(HirToMirError, match="before initialization or twice"):
        lower_hir_to_mir(replace(hir, nodes=nodes))


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


def test_actual_case_18_capability_scope_ends_loan_before_owner_write() -> None:
    source = (
        "module rm1\ncapability io;\n"
        "fn main()->i32 { var x:i32=1; with capability io { "
        "let r: borrow i32=borrow x; print(r); } x=2; return x; }"
    )
    mir = lower_hir_to_mir(lower_checked_local_borrow_source_hir(source))
    instructions = mir.functions[0].blocks[0].instructions
    assert any(instruction.kind == "capability_check" and instruction.capabilities == ("io",)
               for instruction in instructions)
    end = next(effect for effect in mir.functions[0].local_loan_effects if effect.kind == "end")
    assert end.instruction_id < next(
        instruction.instruction_id for instruction in instructions
        if instruction.kind == "copy" and instruction.result == 0
        and instruction.instruction_id > end.instruction_id
    )


def test_other_numeric_type_cannot_be_mislabeled_as_i32() -> None:
    source = SOURCE.replace("let x:i32=1; let r: borrow i32=borrow x;",
                            "let x:i64=1; let r: borrow i64=borrow x;")
    source = source.replace("inspect(r);", "return 0;").replace("return 0; return x;", "return 0;")
    with pytest.raises(LocalBorrowSourceHirError, match="unsupported RM1 source binding type"):
        lower_checked_local_borrow_source_hir(source)
