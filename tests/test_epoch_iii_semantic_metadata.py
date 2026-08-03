from pathlib import Path
import contextlib
import io
import subprocess

from merit.compiler import AssignmentNode, BindingNode, CGenerator, CallNode, CapabilityNode, Checker, ControlFlowNode, DirectCallNode, IfNode, Interpreter, LetNode, NumberNode, OwnershipEffects, ReplaceNode, ReturnNode, SemanticTuple, TypeTable, TypedValue, compile_file, hir, mir, parse


DIRECT_MOVE_PROGRAM = '''module semantic_metadata_move
capability allocate;

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "metadata");
        let destination: Buffer = source;
        print(destination);
        drop(destination);
    }
    return 0;
}'''


def checked(source=DIRECT_MOVE_PROGRAM):
    program = parse(source)
    Checker(program).check()
    return program


def test_type_table_caches_complete_lifecycle_metadata():
    program = parse('''module metadata_types
struct OwnedText { data: Buffer; }
enum MaybeText { Some(OwnedText), None }
fn main() -> i32 { return 0; }''')
    types = TypeTable(program)

    owned_text = types.get("OwnedText")
    assert owned_text is types.get("OwnedText")
    assert (owned_text.kind, owned_text.owned, owned_text.needs_drop, owned_text.copyable, owned_text.drop_strategy) == (
        "struct", True, True, False, "aggregate"
    )
    assert types.get("MaybeText").drop_strategy == "aggregate"
    assert types.get("Buffer").drop_strategy == "buffer"
    assert types.get("Vec__OwnedText").drop_strategy == "vector"
    assert types.get("i64").drop_strategy == "none"


def test_shared_ownership_effects_record_direct_move():
    program = checked()
    ownership = OwnershipEffects(program, TypeTable(program)).function(program.functions[0])
    assert ownership.owned_locals == (("source", "Buffer"), ("destination", "Buffer"))
    assert ownership.explicit_drops == frozenset({"destination"})
    assert ownership.consumed_roots == frozenset({"source"})
    function_mir = mir(program)["functions"][0]
    assert function_mir["explicit_drops"] == ["destination"]
    assert function_mir["consumed_roots"] == ["source"]


def test_semantic_node_view_exposes_typed_dispatch_and_provenance():
    program = parse(DIRECT_MOVE_PROGRAM, "semantic_nodes.mrt")
    capability_statement = program.functions[0]["body"][0]
    assert isinstance(capability_statement, SemanticTuple)
    assert isinstance(capability_statement, ControlFlowNode)
    assert isinstance(capability_statement, CapabilityNode)
    assert isinstance(capability_statement, tuple)
    capability = program.node(capability_statement)
    assert capability.kind == "with_cap"
    assert capability.operand(0) == "allocate"
    assert capability.operands[1] is capability_statement[2]
    assert capability.nested_body is capability_statement[2]
    assert (capability.span.line, capability.span.source_name) == (5, "semantic_nodes.mrt")
    assert capability.related_span is None
    provenance = program.provenance(capability_statement)
    assert provenance.primary == capability.span
    assert provenance.related is None
    program.spans.clear()
    program.related_spans.clear()
    assert program.provenance(capability_statement) == provenance
    binding = program.node(capability.operand(1)[1])
    assert isinstance(binding.raw, BindingNode)
    assert isinstance(binding.raw, LetNode)
    assert (binding.kind, binding.binding_name, binding.declared_type) == ("let", "source", "Buffer")
    assert program.node(binding.initializer).kind == "call"
    call = program.node(binding.initializer)
    assert isinstance(call.raw, CallNode)
    assert isinstance(call.raw, DirectCallNode)
    assert (call.callee_name, len(call.arguments)) == ("buffer_from_string", 2)


def test_ownership_sensitive_accessors_cover_replacement_operands():
    program = parse('''module semantic_replace
fn main() -> i32 {
    var value: i64 = 1;
    replace(value, 2);
    return 0;
}''')
    replacement = program.node(program.functions[0]["body"][1])
    assert isinstance(replacement.raw, AssignmentNode)
    assert isinstance(replacement.raw, ReplaceNode)
    assert replacement.kind == "replace"
    assert program.node(replacement.assignment_target).kind == "var"
    assert program.node(replacement.assigned_value).kind == "number"


def test_control_flow_accessors_expose_named_branches():
    program = parse('''module semantic_control
fn main() -> i32 {
    if 1 { return 1; } else { return 0; }
}''')
    branch = program.node(program.functions[0]["body"][0])
    assert isinstance(branch.raw, IfNode)
    assert branch.kind == "if"
    assert isinstance(program.node(branch.condition).raw, NumberNode)
    assert isinstance(branch.then_body[0], ReturnNode)
    assert program.node(branch.then_body[0]).expression[1] == "1"
    assert program.node(branch.else_body[0]).expression[1] == "0"


def test_hir_exposes_shared_type_semantics():
    program = parse('''module metadata_hir
struct OwnedText { data: Buffer; }
fn main() -> i32 { return 0; }''')
    semantics = hir(program)["type_semantics"]
    assert semantics["OwnedText"]["drop_strategy"] == "aggregate"
    assert semantics["Buffer"]["drop_strategy"] == "buffer"
    assert semantics["i32"]["copyable"] is True


def test_interpreter_recursively_drops_from_shared_metadata():
    program = parse('''module metadata_interpreter
struct OwnedText { data: Buffer; }
enum MaybeText { Some(OwnedText), None }
fn main() -> i32 { return 0; }''')
    interpreter = Interpreter(program)
    bytes_value = TypedValue("Buffer", bytearray(b"owned"))
    struct_value = TypedValue("OwnedText", {"data": bytes_value})
    enum_value = TypedValue("MaybeText", {"variant": "Some", "payload": struct_value})
    vector_value = TypedValue("Vec__MaybeText", [enum_value])
    interpreter.drop_value(vector_value)
    assert vector_value.value == []
    assert bytes_value.value == bytearray()


def test_direct_owned_move_cleanup_matches_interpreter_and_native(tmp_path):
    program = checked()
    generated = CGenerator(program).generate()
    assert "merit_buffer_drop(&source);" not in generated
    assert generated.count("merit_buffer_drop(&destination);") == 1
    statements = mir(program)["functions"][0]["blocks"][0]["statements"]
    assert ("drop_implicit", "source") not in statements

    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(program).run()
    source = tmp_path / "direct_move.mrt"
    executable = tmp_path / "direct_move"
    source.write_text(DIRECT_MOVE_PROGRAM)
    compile_file(source, executable)
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert native.stdout == interpreted.getvalue() == "metadata\n"


def test_shared_effects_cover_nested_consuming_calls():
    program = checked('''module metadata_nested
capability allocate;
fn consume(value: Buffer) -> i64 { let size: i64 = buffer_len(value); drop(value); return size; }
fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "nested");
        print(consume(source));
    }
    return 0;
}''')
    ownership = OwnershipEffects(program, TypeTable(program)).function(next(f for f in program.functions if f["name"] == "main"))
    assert ownership.consumed_roots == frozenset({"source"})
    generated = CGenerator(program).generate()
    main = generated[generated.index("int32_t main"):]
    assert "merit_buffer_drop(&source);" not in main
