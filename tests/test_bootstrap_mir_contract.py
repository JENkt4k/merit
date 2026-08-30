import json

import pytest

from merit.bootstrap.mir_contract import (
    MIR_SCHEMA,
    MirBlock,
    MirContractError,
    MirDestructor,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirParameter,
    MirTerminator,
    MirType,
    SourceSpan,
    canonical_mir_json,
    load_mir_json,
    parse_mir,
)


def i32():
    return MirType("i32")


def sample_module():
    locals_ = (
        MirLocal(0, "value", i32(), source_binding_id=10),
        MirLocal(1, "one", i32()),
        MirLocal(2, "sum", i32()),
        MirLocal(3, "condition", MirType("bool")),
    )
    entry = MirBlock(
        0,
        (
            MirInstruction(0, "const", result=1, value=1),
            MirInstruction(1, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="checked"),
            MirInstruction(2, "contract_check", operands=(3,), contract_kind="postcondition"),
        ),
        MirTerminator("branch", operands=(3,), targets=(1, 2)),
    )
    success = MirBlock(1, (MirInstruction(3, "drop", operands=(0,), ownership="owned"),), MirTerminator("return", operands=(2,)))
    failure = MirBlock(2, (), MirTerminator("unreachable"))
    function = MirFunction("add_one", i32(), locals_, (entry, success, failure), 0, ("math",))
    return MirModule("sample", (function,))


def test_sample_mir_is_canonical_and_round_trips():
    module = sample_module()
    encoded = canonical_mir_json(module)
    assert load_mir_json(encoded) == module
    assert parse_mir(json.loads(encoded)) == module
    assert encoded == canonical_mir_json(module)
    assert json.loads(encoded)["schema"] == MIR_SCHEMA


def test_executable_destructor_is_canonical_and_round_trips():
    target = MirType("struct_i64_destructor_0")
    destructor = MirDestructor(
        target,
        (
            MirLocal(0, "self", target, mutable=True, ownership="mutable_borrow"),
            MirLocal(1, "field", MirType("i64")),
        ),
        (
            MirBlock(
                0,
                (
                    MirInstruction(0, "load_field", result=1, operands=(0,), symbol="field_0"),
                    MirInstruction(1, "print", operands=(1,)),
                ),
                MirTerminator("return"),
            ),
        ),
        0,
    )
    module = MirModule("destructor", (), destructors=(destructor,))
    assert load_mir_json(canonical_mir_json(module)) == module

    with pytest.raises(MirContractError, match="duplicate MIR destructor target"):
        MirModule("duplicate", (), destructors=(destructor, destructor))


def test_callable_ownership_signature_is_canonical_and_round_trips():
    target = MirType("struct_i64_0")
    function = MirFunction(
        "expose",
        target,
        (MirLocal(0, "value", target, mutable=True, ownership="mutable_borrow"),),
        (MirBlock(0, (), MirTerminator("return", operands=(0,))),),
        0,
        parameters=(MirParameter(0, "mutable_borrow"),),
        return_mode="mutable_borrow",
        borrowed_origin=0,
    )
    module = MirModule("callable", (function,))
    encoded = canonical_mir_json(module)
    assert load_mir_json(encoded) == module
    assert json.loads(encoded)["functions"][0]["parameters"] == [
        {"local": 0, "mode": "mutable_borrow"}
    ]


def test_borrowed_return_requires_compatible_parameter_origin():
    target = MirType("struct_i64_0")
    local = MirLocal(0, "value", target, ownership="borrowed")
    block = MirBlock(0, (), MirTerminator("return", operands=(0,)))
    with pytest.raises(MirContractError, match="parameter origin"):
        MirFunction("expose", target, (local,), (block,), 0, return_mode="borrowed")
    with pytest.raises(MirContractError, match="mutable-borrow origin"):
        MirFunction(
            "expose_mut", target, (local,), (block,), 0,
            parameters=(MirParameter(0, "borrowed"),),
            return_mode="mutable_borrow", borrowed_origin=0,
        )


def test_canonical_json_is_independent_of_mapping_order():
    data = sample_module().to_data()
    reordered = {"functions": data["functions"], "name": data["name"], "schema": data["schema"]}
    assert canonical_mir_json(parse_mir(reordered)) == canonical_mir_json(sample_module())


def test_nested_types_and_source_provenance_are_preserved():
    type_ = MirType("Result", (MirType("Vec", (MirType("Money"),)), MirType("Error")))
    local = MirLocal(0, "result", type_, ownership="owned", source_binding_id=42)
    instruction = MirInstruction(0, "construct", result=0, symbol="Ok", span=SourceSpan(4, 7), ownership="owned")
    block = MirBlock(0, (instruction,), MirTerminator("return", operands=(0,), span=SourceSpan(12, 3)))
    module = MirModule("nested", (MirFunction("main", type_, (local,), (block,), 0),))
    assert load_mir_json(canonical_mir_json(module)) == module


@pytest.mark.parametrize(
    "factory, message",
    [
        (lambda: SourceSpan(-1, 0), "non-negative"),
        (lambda: MirType(""), "non-empty"),
        (lambda: MirLocal(-1, "x", i32()), "non-negative"),
        (lambda: MirLocal(0, "", i32()), "non-empty"),
        (lambda: MirLocal(0, "x", i32(), ownership="unknown"), "unknown ownership"),
        (lambda: MirInstruction(-1, "nop"), "non-negative"),
        (lambda: MirInstruction(0, "unknown"), "unknown MIR instruction"),
        (lambda: MirInstruction(0, "nop", ownership="unknown"), "unknown ownership"),
        (lambda: MirInstruction(0, "nop", numeric_policy="unknown"), "unknown numeric"),
        (lambda: MirInstruction(0, "nop", conversion_policy="unknown"), "unknown conversion"),
        (lambda: MirInstruction(0, "nop", contract_kind="unknown"), "unknown contract"),
        (lambda: MirInstruction(0, "nop", capabilities=("io", "io")), "unique"),
        (lambda: MirTerminator("unknown"), "unknown MIR terminator"),
        (lambda: MirTerminator("jump"), "exactly one target"),
        (lambda: MirTerminator("branch", operands=(0,), targets=(1,)), "two targets"),
        (lambda: MirTerminator("unreachable", operands=(0,)), "cannot carry"),
    ],
)
def test_record_level_contract_failures(factory, message):
    with pytest.raises(MirContractError, match=message):
        factory()


def make_function(*, locals_=None, blocks=None, entry=0, capabilities=()):
    if locals_ is None:
        locals_ = (MirLocal(0, "value", i32()),)
    if blocks is None:
        blocks = (MirBlock(0, (), MirTerminator("return", operands=(0,))),)
    return MirFunction("main", i32(), tuple(locals_), tuple(blocks), entry, tuple(capabilities))


def test_duplicate_function_names_are_rejected():
    function = make_function()
    with pytest.raises(MirContractError, match="duplicate MIR function"):
        MirModule("m", (function, function))


def test_duplicate_local_ids_are_rejected():
    local = MirLocal(0, "x", i32())
    with pytest.raises(MirContractError, match="duplicate MIR local"):
        make_function(locals_=(local, local))


def test_duplicate_block_ids_are_rejected():
    block = MirBlock(0, (), MirTerminator("unreachable"))
    with pytest.raises(MirContractError, match="duplicate MIR block"):
        make_function(blocks=(block, block))


def test_duplicate_instruction_ids_are_rejected_across_blocks():
    blocks = (
        MirBlock(0, (MirInstruction(0, "nop"),), MirTerminator("jump", targets=(1,))),
        MirBlock(1, (MirInstruction(0, "nop"),), MirTerminator("return", operands=(0,))),
    )
    with pytest.raises(MirContractError, match="duplicate MIR instruction"):
        make_function(blocks=blocks)


def test_entry_block_must_exist():
    with pytest.raises(MirContractError, match="entry block"):
        make_function(entry=4)


def test_instruction_order_is_explicit_and_strict():
    block = MirBlock(0, (MirInstruction(2, "nop"), MirInstruction(1, "nop")), MirTerminator("return", operands=(0,)))
    with pytest.raises(MirContractError, match="strictly ordered"):
        make_function(blocks=(block,))


def test_unknown_local_reads_and_writes_are_rejected():
    with pytest.raises(MirContractError, match="writes unknown local"):
        make_function(blocks=(MirBlock(0, (MirInstruction(0, "const", result=9),), MirTerminator("return", operands=(0,))),))
    with pytest.raises(MirContractError, match="reads unknown local"):
        make_function(blocks=(MirBlock(0, (MirInstruction(0, "copy", result=0, operands=(9,)),), MirTerminator("return", operands=(0,))),))


def test_unknown_block_targets_are_rejected():
    with pytest.raises(MirContractError, match="unknown block"):
        make_function(blocks=(MirBlock(0, (), MirTerminator("jump", targets=(4,))),))


def test_unreachable_blocks_are_rejected():
    blocks = (
        MirBlock(0, (), MirTerminator("return", operands=(0,))),
        MirBlock(1, (), MirTerminator("unreachable")),
    )
    with pytest.raises(MirContractError, match="unreachable MIR blocks"):
        make_function(blocks=blocks)


@pytest.mark.parametrize(
    "instruction, message",
    [
        (MirInstruction(0, "binary", result=0, operands=(0, 0)), "explicit numeric"),
        (MirInstruction(0, "convert", result=0, operands=(0,)), "explicit conversion"),
        (MirInstruction(0, "contract_check", operands=(0,)), "explicit contract"),
        (MirInstruction(0, "capability_check"), "at least one capability"),
        (MirInstruction(0, "move"), "require an operand"),
        (MirInstruction(0, "borrow"), "require an operand"),
        (MirInstruction(0, "drop"), "require an operand"),
        (MirInstruction(0, "deallocate"), "require an operand"),
    ],
)
def test_semantic_instruction_metadata_is_mandatory(instruction, message):
    block = MirBlock(0, (instruction,), MirTerminator("return", operands=(0,)))
    with pytest.raises(MirContractError, match=message):
        make_function(blocks=(block,))


def test_switch_shape_and_reachability():
    blocks = (
        MirBlock(0, (), MirTerminator("switch", operands=(0,), targets=(1, 2, 3), cases=(10, 20))),
        MirBlock(1, (), MirTerminator("return", operands=(0,))),
        MirBlock(2, (), MirTerminator("return", operands=(0,))),
        MirBlock(3, (), MirTerminator("return", operands=(0,))),
    )
    assert make_function(blocks=blocks).entry_block == 0


def test_invalid_json_and_root_are_rejected():
    with pytest.raises(MirContractError, match="invalid MIR JSON"):
        load_mir_json("{")
    with pytest.raises(MirContractError, match="root must be an object"):
        load_mir_json("[]")


def test_wrong_schema_and_malformed_collections_are_rejected():
    with pytest.raises(MirContractError, match="expected MIR schema"):
        parse_mir({"schema": "wrong", "name": "m", "functions": []})
    with pytest.raises(MirContractError, match="functions must be a list"):
        parse_mir({"schema": MIR_SCHEMA, "name": "m", "functions": {}})


def test_explicit_numeric_conversion_contract_and_capability_policies_survive_round_trip():
    locals_ = tuple(MirLocal(index, name, i32()) for index, name in enumerate(("a", "b", "sum", "converted", "condition")))
    instructions = (
        MirInstruction(0, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="exact"),
        MirInstruction(1, "convert", result=3, operands=(2,), conversion_policy="round"),
        MirInstruction(2, "contract_check", operands=(4,), contract_kind="precondition"),
        MirInstruction(3, "capability_check", capabilities=("filesystem.read",)),
    )
    module = MirModule("policies", (MirFunction("main", i32(), locals_, (MirBlock(0, instructions, MirTerminator("return", operands=(3,))),), 0, ("filesystem.read",)),))
    decoded = load_mir_json(canonical_mir_json(module))
    assert decoded.functions[0].blocks[0].instructions == instructions
    assert decoded.functions[0].capabilities == ("filesystem.read",)
