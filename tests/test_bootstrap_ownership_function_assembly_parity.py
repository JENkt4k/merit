from merit.bootstrap.mir_contract import canonical_mir_json
from merit.bootstrap.mir_function_ownership_assembly_parity import (
    lower_native_ownership_whole_function_assembly,
)

SOURCE = "module demo\nfn compute()->i64 { let r:i64=1; return 7; }\n"


def _span(text: str):
    start = SOURCE.index(text)
    return start, len(text)


def _records():
    fn_start, fn_len = _span("compute")
    r_start, r_len = _span("r:i64")
    r_start = r_start
    r_len = 1
    one_start, one_len = _span("1")
    seven_start, seven_len = _span("7")
    body = (
        (1, fn_start, fn_len, 0, -1, -1, -1, fn_start, fn_len, 0, 1, 0, -1, 0, -1, 0),
        (2, r_start, r_len, 0, -1, -1, -1, r_start, r_len, 0, 1, 0, 0, 0, -1, 0),
        (3, 0, 0, 1, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 0, 1),
        (3, 0, 0, 2, -1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 1, 2),
        (4, one_start, one_len, 0, 1, -1, -1, -1, 0, 0, 1, 0, -1, 0, 0, 0),
        (6, one_start, one_len, 1, 0, 1, -1, -1, 0, 0, 0, 0, 0, 0, 1, 1),
        (4, seven_start, seven_len, 2, 2, -1, -1, -1, 0, 0, 1, 0, -1, 0, 2, 2),
    )
    sources = (
        (0, 2, 0, 0, -1, -1, -1, -1),
        (1, 2, 1, 0, -1, -1, -1, -1),
        (2, 2, 2, 0, -1, -1, -1, -1),
        (3, 3, 1, 0, -1, -1, 0, -1),
    )
    ownership_bindings = ((0, 0, 1, 0),)
    ownership_records = (
        (1, -1, 0, -1, 0, 0, 0, 1),
        (3, 3, 0, -1, 0, 0, 1, 3),
    )
    cfg = (
        (10, 0, -1, -1, -1, 0, 0),
        (15, 0, 2, -1, -1, 0, 0),
    )
    placements = ((0, 0, 0), (0, 1, 1), (0, 2, 2), (0, 3, 3))
    return body, sources, ownership_bindings, ownership_records, cfg, placements


def test_ownership_provenance_materializes_explicit_drop_and_owned_local():
    body, sources, bindings, records, cfg, placements = _records()
    module = lower_native_ownership_whole_function_assembly(
        source=SOURCE,
        module_name="demo",
        body_records=body,
        contract_records=(),
        contract_locals=(),
        instruction_sources=sources,
        ownership_bindings=bindings,
        ownership_records=records,
        cfg_records=cfg,
        placements=placements,
        capability_ids=(),
        capability_names={},
    )
    function = module.functions[0]
    assert function.locals[0].name == "r"
    assert function.locals[0].ownership == "owned"
    assert [instruction.instruction_id for instruction in function.blocks[0].instructions] == [0, 1, 2, 3]
    assert [instruction.kind for instruction in function.blocks[0].instructions] == ["const", "copy", "const", "drop"]
    assert function.blocks[0].instructions[-1].operands == (0,)
    assert function.blocks[0].instructions[-1].ownership == "owned"
    assert function.blocks[0].terminator.kind == "return"
    assert function.blocks[0].terminator.operands == (2,)
    data = canonical_mir_json(module)
    assert '\"kind\":\"drop\"' in data
    assert '\"ownership\":\"owned\"' in data
