import contextlib
import io
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, LayoutEngine, VEC_INTRINSICS, VECTOR_INTRINSIC_NAMES, capability_requirements, compile_file, is_copyable_type, parse, type_needs_drop, type_semantics, vec_return_type
from merit.project.build import build, check, interpret
from merit.project.loader import load_project


VEC_I64_PROGRAM = r'''
module vec_i64_acceptance
capability allocate;

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        var values: Vec<i64> = vec_new<i64>(a, 2);
        vec_push<i64>(values, 7);
        vec_push<i64>(values, 11);
        vec_set<i64>(values, 1, 13);
        print(vec_len<i64>(values));
        print(vec_get<i64>(values, 0));
        print(vec_pop<i64>(values));
        drop(values);
    }
    return 0;
}
'''


VEC_GENERIC_API_PROGRAM = r'''
module vec_generic_api_acceptance
capability allocate;

struct OwnedText {
    data: Buffer;
}

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        var values: Vec<i64> = vec_new<i64>(a, 2);
        vec_push<i64>(values, 3);
        vec_push<i64>(values, 8);
        print(vec_len<i64>(values));
        print(vec_get<i64>(values, 1));

        var texts: Vec<OwnedText> = vec_new<OwnedText>(a, 1);
        let b: Buffer = buffer_from_string(a, "generic");
        let item: OwnedText = OwnedText { data: b };
        vec_push<OwnedText>(texts, item);
        let out: OwnedText = vec_pop<OwnedText>(texts);
        print(buffer_len(out.data));

        drop(out);
        drop(texts);
        drop(values);
    }
    return 0;
}
'''


VEC_PAIR_PROGRAM = r'''
module vec_pair_acceptance
capability allocate;

struct Pair<T, U> {
    first: T;
    second: U;
}

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        var pairs: Vec<Pair<i64, i32>> = vec_new<Pair<i64, i32>>(a, 1);
        let p: Pair<i64, i32> = Pair<i64, i32> { first: 21, second: 5 };
        vec_push<Pair<i64, i32>>(pairs, p);
        let got: Pair<i64, i32> = vec_get<Pair<i64, i32>>(pairs, 0);
        print(got.first);
        print(got.second);
        drop(pairs);
    }
    return 0;
}
'''


VEC_BUFFER_PROGRAM = r'''
module vec_buffer_acceptance
capability allocate;

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        var buffers: Vec<Buffer> = vec_new<Buffer>(a, 2);
        let first: Buffer = buffer_from_string(a, "ab");
        let second: Buffer = buffer_from_string(a, "wxyz");
        vec_push<Buffer>(buffers, first);
        vec_push<Buffer>(buffers, second);
        print(vec_len<Buffer>(buffers));
        let last: Buffer = vec_pop<Buffer>(buffers);
        print(buffer_len(last));
        drop(last);
        drop(buffers);
    }
    return 0;
}
'''


STRUCT_OWNED_FIELD_PROGRAM = r'''
module struct_owned_field_acceptance
capability allocate;

struct OwnedText {
    data: Buffer;
}

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        let text: Buffer = buffer_from_string(a, "owned");
        let wrapped: OwnedText = OwnedText { data: text };
        print(buffer_len(wrapped.data));
        drop(wrapped);
    }
    return 0;
}
'''


VEC_OWNED_STRUCT_PROGRAM = r'''
module vec_owned_struct_acceptance
capability allocate;

struct OwnedText {
    data: Buffer;
}

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        var texts: Vec<OwnedText> = vec_new<OwnedText>(a, 2);
        let first_buffer: Buffer = buffer_from_string(a, "first");
        let second_buffer: Buffer = buffer_from_string(a, "second");
        let first: OwnedText = OwnedText { data: first_buffer };
        let second: OwnedText = OwnedText { data: second_buffer };
        vec_push<OwnedText>(texts, first);
        vec_push<OwnedText>(texts, second);
        print(vec_len<OwnedText>(texts));
        let last: OwnedText = vec_pop<OwnedText>(texts);
        print(buffer_len(last.data));
        drop(last);
        drop(texts);
    }
    return 0;
}
'''


ENUM_VEC_PROGRAM = r'''
module enum_vec_acceptance
capability allocate;

enum Error {
    Bad
}

enum Option<T> {
    Some(T),
    None
}

enum Result<T, E> {
    Ok(T),
    Err(E)
}

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();

        var values: Vec<i64> = vec_new<i64>(a, 2);
        vec_push<i64>(values, 31);
        vec_push<i64>(values, 32);
        let maybe: Option<Vec<i64>> = Option<Vec<i64>>::Some(values);
        match (maybe) {
            Option<Vec<i64>>::Some(inner) => {
                print(vec_len<i64>(inner));
                print(vec_get<i64>(inner, 1));
                drop(inner);
            }
            Option<Vec<i64>>::None => {
                print(0);
            }
        }

        var result_values: Vec<i64> = vec_new<i64>(a, 1);
        vec_push<i64>(result_values, 44);
        let outcome: Result<Vec<i64>, Error> = Result<Vec<i64>, Error>::Ok(result_values);
        match (outcome) {
            Result<Vec<i64>, Error>::Ok(ok_values) => {
                print(vec_get<i64>(ok_values, 0));
                drop(ok_values);
            }
            Result<Vec<i64>, Error>::Err(error) => {
                print(0);
            }
        }
    }
    return 0;
}
'''


def run_interpreter_and_native(source_text: str, tmp_path: Path, name: str) -> str:
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(parse(source_text)).run()
    source = tmp_path / f'{name}.mrt'
    source.write_text(source_text)
    _, _, _, executable = compile_file(source, tmp_path / name)
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted.getvalue() == native
    return native


def test_vec_i64_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(VEC_I64_PROGRAM, tmp_path, 'vec_i64') == '2\n7\n13\n'


def test_vec_intrinsic_metadata_covers_public_operations():
    assert tuple(VEC_INTRINSICS) == VECTOR_INTRINSIC_NAMES
    assert vec_return_type('new', 'i64') == 'Vec__i64'
    assert vec_return_type('get', 'OwnedText') == 'OwnedText'
    assert vec_return_type('push', 'OwnedText') == 'void'
    assert VEC_INTRINSICS['new'].requires_allocate
    assert VEC_INTRINSICS['push'].receiver_mode == 'borrow_mut'
    assert VEC_INTRINSICS['get'].rejects_owned_result_copy


def test_type_semantics_classifies_owned_and_copy_values():
    program = parse(r'''
module type_semantics_acceptance
struct OwnedText {
    data: Buffer;
}
enum Error {
    Bad
}
enum Option<T> {
    Some(T),
    None
}
fn consume_option(value: Option<Vec<i64>>) -> i32 {
    return 0;
}
fn main() -> i32 {
    return 0;
}
''')
    assert type_semantics('i64', program).copyable
    assert type_semantics('Buffer', program).needs_drop
    assert type_semantics('Vec__i64', program).owned
    assert type_semantics('OwnedText', program).owned
    assert type_semantics('OwnedText', program).needs_drop
    assert type_semantics('Error', program).copyable
    assert type_semantics('Option__Vec__i64', program).needs_drop
    assert type_needs_drop('Option__Vec__i64', program)
    assert not type_needs_drop('Error', program)
    assert is_copyable_type('Error', program)
    assert not is_copyable_type('OwnedText', program)


def test_generated_drop_uses_shared_type_semantics():
    c = CGenerator(parse(ENUM_VEC_PROGRAM))
    assert c.drop_field_stmt('value', 'Option__Vec__i64') == 'merit_drop_Option__Vec__i64(&value);'
    assert c.drop_binding_line('    ', 'values', 'Vec__i64') == '    merit_vec_drop__i64(&values);'
    assert c.drop_binding_line('    ', 'error', 'Error') == '    /* deterministic drop error */'


def test_vec_generic_api_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(VEC_GENERIC_API_PROGRAM, tmp_path, 'vec_generic_api') == '2\n8\n7\n'


def test_unsupported_generic_call_is_rejected():
    bad = VEC_GENERIC_API_PROGRAM.replace('vec_new<i64>(a, 2)', 'unknown_generic<i64>(a, 2)')
    with pytest.raises(CompileError, match='unsupported generic call unknown_generic<i64>'):
        Checker(parse(bad)).check()


def test_vec_generic_struct_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(VEC_PAIR_PROGRAM, tmp_path, 'vec_pair') == '21\n5\n'


def test_vec_buffer_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(VEC_BUFFER_PROGRAM, tmp_path, 'vec_buffer') == '2\n4\n'


def test_struct_owned_field_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(STRUCT_OWNED_FIELD_PROGRAM, tmp_path, 'struct_owned') == '5\n'


def test_vec_owned_struct_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(VEC_OWNED_STRUCT_PROGRAM, tmp_path, 'vec_owned_struct') == '2\n6\n'


def test_vec_headers_include_layout_assertions():
    header = CGenerator(parse(VEC_OWNED_STRUCT_PROGRAM)).header()
    assert '/* Merit layout vector Vec__OwnedText hash ' in header
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, data) == 0' in header
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, len) == sizeof(void *)' in header
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, cap) == sizeof(void *) + sizeof(size_t)' in header
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, allocator) == sizeof(void *) + sizeof(size_t) * 2' in header
    assert '_Static_assert(sizeof(merit_Vec__OwnedText) == 32' in header


@pytest.mark.parametrize(("constructor", "identity"), [("system_allocator", "system"), ("portable_allocator", "portable")])
def test_vec_runtime_retains_and_dispatches_through_allocator(tmp_path, constructor, identity):
    source_text = f'''module allocator_identity
capability allocate;
fn main()->i32 {{ with capability allocate {{ let allocator:Allocator={constructor}(); var values:Vec<i64>=vec_new<i64>(allocator,2); vec_push<i64>(values,7); print(vec_len<i64>(values)); drop(values); }} return 0; }}'''
    program = parse(source_text)
    Checker(program).check()
    capability = program.node(program.functions[0].body[0])
    allocator_binding = program.node(capability.nested_body[0])
    vector_binding = program.node(capability.nested_body[1])
    interpreter = Interpreter(program)
    allocator = interpreter.eval(allocator_binding.initializer, {})
    vector = interpreter.eval(vector_binding.initializer, {"allocator": allocator})
    assert vector.allocator == identity
    generated = CGenerator(program).generate()
    assert f"merit_{constructor}" in generated
    assert "v.allocator=a" in generated
    assert "merit_allocator_realloc(v->allocator" in generated
    assert "merit_allocator_free(v->allocator" in generated
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted): Interpreter(program).run()
    source = tmp_path / f"{identity}_allocator.mrt"; executable = tmp_path / f"{identity}_allocator"
    source.write_text(source_text); compile_file(source, executable)
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert interpreted.getvalue() == native == "1\n"


def test_vec_layout_report_includes_hashes():
    layouts = {entry['name']: entry for entry in LayoutEngine(parse(VEC_OWNED_STRUCT_PROGRAM)).all()}
    vector = layouts['Vec__OwnedText']
    assert vector['kind'] == 'vector'
    assert vector['size'] == 32
    assert [field['offset'] for field in vector['fields']] == [0, 8, 16, 24]
    assert vector['fields'][-1]['name'] == 'allocator'
    assert len(vector['layout_hash']) == 24


def test_enum_headers_include_layout_assertions():
    header = CGenerator(parse(ENUM_VEC_PROGRAM)).header()
    assert '/* Merit layout enum Option__Vec__i64 hash ' in header
    assert '/* Merit layout enum Result__Vec__i64__Error hash ' in header
    assert '_Static_assert(__builtin_offsetof(merit_Option__Vec__i64, tag) == 0' in header
    assert '_Static_assert(__builtin_offsetof(merit_Option__Vec__i64, data) >= sizeof(merit_Option__Vec__i64_tag)' in header
    assert '_Static_assert(__builtin_offsetof(merit_Result__Vec__i64__Error, tag) == 0' in header
    assert '_Static_assert(__builtin_offsetof(merit_Result__Vec__i64__Error, data) >= sizeof(merit_Result__Vec__i64__Error_tag)' in header


def test_enum_layout_report_includes_payload_hashes():
    layouts = {entry['name']: entry for entry in LayoutEngine(parse(ENUM_VEC_PROGRAM)).all()}
    option = layouts['Option__Vec__i64']
    result = layouts['Result__Vec__i64__Error']
    assert option['kind'] == 'enum'
    assert option['tag']['offset'] == 0
    assert option['payload_offset'] == 8
    assert option['payload_size'] == 32
    assert len(option['layout_hash']) == 24
    assert result['payload_size'] == 32


def test_enum_vec_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(ENUM_VEC_PROGRAM, tmp_path, 'enum_vec') == '2\n32\n44\n'


def test_vec_allocation_requires_capability():
    bad = VEC_I64_PROGRAM.replace('with capability allocate {\n        ', '').replace('\n    }\n    return 0;', '\n    return 0;')
    with pytest.raises(CompileError, match='requires capabilities'):
        Checker(parse(bad)).check()


def test_vec_mutation_requires_mutable_binding():
    bad = VEC_I64_PROGRAM.replace('var values: Vec<i64>', 'let values: Vec<i64>')
    with pytest.raises(CompileError, match='borrow_mut argument values is not mutable'):
        Checker(parse(bad)).check()


def test_vec_push_moves_struct_value():
    bad = VEC_PAIR_PROGRAM.replace(
        'let got: Pair<i64, i32> = vec_get<Pair<i64, i32>>(pairs, 0);',
        'print(p.first);\n        let got: Pair<i64, i32> = vec_get<Pair<i64, i32>>(pairs, 0);',
    )
    with pytest.raises(CompileError, match='moved value p'):
        Checker(parse(bad)).check()


def test_vec_push_moves_buffer_value():
    bad = VEC_BUFFER_PROGRAM.replace(
        'print(vec_len<Buffer>(buffers));',
        'print(buffer_len(first));\n        print(vec_len<Buffer>(buffers));',
    )
    with pytest.raises(CompileError, match='moved value first'):
        Checker(parse(bad)).check()


def test_vec_get_rejects_owned_buffer_copy():
    bad = VEC_BUFFER_PROGRAM.replace(
        'let last: Buffer = vec_pop<Buffer>(buffers);',
        'let last: Buffer = vec_get<Buffer>(buffers, 0);',
    )
    with pytest.raises(CompileError, match='cannot copy owned element Buffer'):
        Checker(parse(bad)).check()


def test_struct_init_moves_owned_field_source():
    bad = STRUCT_OWNED_FIELD_PROGRAM.replace(
        'print(buffer_len(wrapped.data));',
        'print(buffer_len(text));\n        print(buffer_len(wrapped.data));',
    )
    with pytest.raises(CompileError, match='moved value text'):
        Checker(parse(bad)).check()


def test_vec_get_rejects_owned_struct_copy():
    bad = VEC_OWNED_STRUCT_PROGRAM.replace(
        'let last: OwnedText = vec_pop<OwnedText>(texts);',
        'let last: OwnedText = vec_get<OwnedText>(texts, 0);',
    )
    with pytest.raises(CompileError, match='cannot copy owned element OwnedText'):
        Checker(parse(bad)).check()


def test_enum_constructor_moves_owned_payload_source():
    bad = ENUM_VEC_PROGRAM.replace(
        'match (maybe) {',
        'print(vec_len<i64>(values));\n        match (maybe) {',
    )
    with pytest.raises(CompileError, match='moved value values'):
        Checker(parse(bad)).check()


def test_match_consumes_owned_enum_subject():
    bad = ENUM_VEC_PROGRAM.replace(
        'var result_values: Vec<i64> = vec_new<i64>(a, 1);',
        'print(maybe);\n\n        var result_values: Vec<i64> = vec_new<i64>(a, 1);',
    )
    with pytest.raises(CompileError, match='moved value maybe'):
        Checker(parse(bad)).check()


def test_generic_collections_project_interpreter_and_native(tmp_path):
    project = load_project(Path('examples/projects/generic_collections/Merit.toml'))
    check(project)
    output = interpret(project)
    _, _, executable = build(project, tmp_path / 'generic_collections')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert native == output == '2\n7\n13\n21\n5\n2\n4\n5\n2\n6\n2\n32\n44\n1\n1\n0\n7\n'


def test_allocator_compatibility_has_interpreter_native_parity(tmp_path):
    source_text='''module allocator_compatibility
fn main()->i32 { let system:Allocator=system_allocator(); let same:Allocator=system_allocator(); let portable:Allocator=portable_allocator(); print(allocator_compatible(system,same)); print(allocator_compatible(system,portable)); return 0; }'''
    program=parse(source_text);Checker(program).check()
    interpreted=io.StringIO()
    with contextlib.redirect_stdout(interpreted):Interpreter(program).run()
    source=tmp_path/'allocator_compatibility.mrt';executable=tmp_path/'allocator_compatibility'
    source.write_text(source_text);compile_file(source,executable)
    native=subprocess.run([str(executable)],check=True,text=True,capture_output=True).stdout
    assert interpreted.getvalue() == native == '1\n0\n'


def test_allocator_compatibility_requires_allocator_arguments():
    source='module invalid_allocator_compatibility\nfn main()->i32 { let allocator:Allocator=system_allocator(); return allocator_compatible(allocator,1); }'
    with pytest.raises(CompileError,match='argument 1 expects Allocator'):
        Checker(parse(source)).check()


def test_numeric_literal_does_not_coerce_to_nonnumeric_user_parameter():
    source='module invalid_literal_coercion\nfn use(value:Allocator)->i32 { return 0; }\nfn main()->i32 { return use(1); }'
    with pytest.raises(CompileError,match='argument value expects Allocator'):
        Checker(parse(source)).check()


def test_vec_transfer_steals_compatible_storage(tmp_path):
    source='''module vector_transfer
capability allocate;
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var destination:Vec<i64>=vec_new<i64>(allocator,0); var source:Vec<i64>=vec_new<i64>(allocator,2); vec_push<i64>(source,7); vec_push<i64>(source,11); vec_transfer<i64>(destination,source); print(vec_len<i64>(destination)); print(vec_get<i64>(destination,1)); print(vec_len<i64>(source)); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'vector_transfer') == '2\n11\n0\n'


def test_vec_transfer_sequences_destination_before_source_in_generated_c():
    source='''module vector_transfer_order
capability allocate;
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var destination:Vec<i64>=vec_new<i64>(allocator,0); var source:Vec<i64>=vec_new<i64>(allocator,0); vec_transfer<i64>(destination,source); } return 0; }'''
    program=parse(source);Checker(program).check();generated=CGenerator(program).generate()
    destination='_merit_vec_transfer_destination_0 = &destination;'
    source_address='_merit_vec_transfer_source_0 = &source;'
    call='merit_vec_transfer__i64(_merit_vec_transfer_destination_0, _merit_vec_transfer_source_0);'
    assert generated.index(destination) < generated.index(source_address) < generated.index(call)


def test_vec_transfer_preserves_owned_element_drop_obligations(tmp_path):
    source='''module owned_vector_transfer
capability allocate;
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var destination:Vec<Marker>=vec_new<Marker>(allocator,0); var source:Vec<Marker>=vec_new<Marker>(allocator,1); let marker:Marker=Marker{number:41}; vec_push<Marker>(source,marker); vec_transfer<Marker>(destination,source); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'owned_vector_transfer') == '41\n'


def test_vec_transfer_rejects_aliasing_at_compile_time():
    source='''module aliased_vector_transfer
capability allocate;
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var values:Vec<i64>=vec_new<i64>(allocator,0); vec_transfer<i64>(values,values); } return 0; }'''
    with pytest.raises(CompileError,match='M7305: vector transfer source aliases destination values'):
        Checker(parse(source)).check()


@pytest.mark.parametrize(
    ('destination','expected'),
    [('vec_new<i64>(portable,0)','incompatible vector allocators'),('vec_new<i64>(system,1)','vector transfer destination is not empty')],
)
def test_vec_transfer_runtime_contracts_match_native_failures(tmp_path,destination,expected):
    destination_setup=destination
    push_destination='vec_push<i64>(target,3);' if 'system,1' in destination else ''
    source=f'''module invalid_vector_transfer
capability allocate;
fn main()->i32 {{ with capability allocate {{ let system:Allocator=system_allocator(); let portable:Allocator=portable_allocator(); var target:Vec<i64>={destination_setup}; {push_destination} var values:Vec<i64>=vec_new<i64>(system,1); vec_push<i64>(values,7); vec_transfer<i64>(target,values); }} return 0; }}'''
    program=parse(source);Checker(program).check()
    with pytest.raises(RuntimeError,match=expected):Interpreter(program).run()
    path=tmp_path/'invalid_transfer.mrt';executable=tmp_path/'invalid_transfer';path.write_text(source);compile_file(path,executable)
    native=subprocess.run([str(executable)],text=True,capture_output=True)
    assert native.returncode == 90
    assert expected in native.stderr


def test_vec_allocator_allows_transfer_compatibility_preflight(tmp_path):
    source='''module vector_allocator_preflight
capability allocate;
fn main()->i32 { with capability allocate { let system:Allocator=system_allocator(); let portable:Allocator=portable_allocator(); var left:Vec<i64>=vec_new<i64>(system,0); var same:Vec<i64>=vec_new<i64>(system,0); var other:Vec<i64>=vec_new<i64>(portable,0); print(allocator_compatible(vec_allocator<i64>(left),vec_allocator<i64>(same))); print(allocator_compatible(vec_allocator<i64>(left),vec_allocator<i64>(other))); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'vector_allocator_preflight') == '1\n0\n'


def test_nested_vectors_preserve_move_and_pop_semantics(tmp_path):
    source='''module nested_vectors
capability allocate;
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var inner:Vec<i64>=vec_new<i64>(allocator,1); vec_push<i64>(inner,47); var outer:Vec<Vec<i64>>=vec_new<Vec<i64>>(allocator,1); vec_push<Vec<i64>>(outer,inner); print(vec_len<Vec<i64>>(outer)); let restored:Vec<i64>=vec_pop<Vec<i64>>(outer); print(vec_get<i64>(restored,0)); print(vec_len<Vec<i64>>(outer)); drop(restored); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'nested_vectors') == '1\n47\n0\n'


def test_nested_vector_cleanup_drops_owned_elements_once(tmp_path):
    source='''module nested_vector_cleanup
capability allocate;
stable("marker-v1") struct Marker { number:i32; }
destructor Marker { print(self.number); }
fn main()->i32 { with capability allocate { let allocator:Allocator=system_allocator(); var inner:Vec<Marker>=vec_new<Marker>(allocator,1); let marker:Marker=Marker{number:53}; vec_push<Marker>(inner,marker); var outer:Vec<Vec<Marker>>=vec_new<Vec<Marker>>(allocator,1); vec_push<Vec<Marker>>(outer,inner); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'nested_vector_cleanup') == '53\n'


def test_buffer_retains_and_dispatches_through_allocator(tmp_path):
    source='''module buffer_allocator_identity
capability allocate;
fn main()->i32 { with capability allocate { let portable:Allocator=portable_allocator(); let system:Allocator=system_allocator(); var data:Buffer=buffer_from_string(portable,"abc"); buffer_push(data,100); print(allocator_compatible(buffer_allocator(data),portable)); print(allocator_compatible(buffer_allocator(data),system)); print(buffer_len(data)); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'buffer_allocator_identity') == '1\n0\n4\n'
    generated=CGenerator(parse(source)).generate()
    assert 'merit_allocator_realloc(b->allocator' in generated
    assert 'merit_allocator_free(b->allocator' in generated


def test_file_read_buffer_retains_requested_allocator(tmp_path):
    payload=tmp_path/'payload.bin';payload.write_bytes(b'abc')
    source=f'''module file_buffer_allocator
capability allocate;
capability file_read;
fn main()->i32 {{ with capability allocate {{ let portable:Allocator=portable_allocator(); with capability file_read {{ let result:FileReadResult=file_read(portable,"{payload}"); match (result) {{ ReadOk(data)=>{{ print(allocator_compatible(buffer_allocator(data),portable)); print(buffer_len(data)); drop(data); }} ReadErr(error)=>{{ print(0); }} }} }} }} return 0; }}'''
    assert run_interpreter_and_native(source,tmp_path,'file_buffer_allocator') == '1\n3\n'


def test_file_read_requires_allocation_capability_for_result_buffer():
    source='''module file_read_allocate
capability allocate;
capability file_read;
fn main()->i32 { let allocator:Allocator=system_allocator(); with capability file_read { let result:FileReadResult=file_read(allocator,"missing"); } return 0; }'''
    with pytest.raises(CompileError,match=r"M2003: call to file_read requires capabilities \['allocate'\]"):
        Checker(parse(source)).check()


def test_file_read_audit_reports_filesystem_and_allocation_hazards():
    program=parse('module file_read_audit\ncapability allocate;\ncapability file_read;\nfn main()->i32 { return 0; }')
    entries={(entry['capability'],entry['hazard']) for entry in capability_requirements(program) if entry['operation']=='file_read'}
    assert entries == {('file_read','filesystem_read'),('allocate','allocation')}


def test_legacy_i64vec_retains_and_dispatches_through_allocator(tmp_path):
    source='''module i64vec_allocator_identity
capability allocate;
fn main()->i32 { with capability allocate { let portable:Allocator=portable_allocator(); let system:Allocator=system_allocator(); var values:I64Vec=i64vec_new(portable,1); i64vec_push(values,61); print(allocator_compatible(i64vec_allocator(values),portable)); print(allocator_compatible(i64vec_allocator(values),system)); print(i64vec_get(values,0)); } return 0; }'''
    assert run_interpreter_and_native(source,tmp_path,'i64vec_allocator_identity') == '1\n0\n61\n'
    generated=CGenerator(parse(source)).generate()
    assert 'merit_allocator_realloc(v->allocator' in generated
    assert 'merit_allocator_free(v->allocator' in generated


@pytest.mark.parametrize(
    'declaration_and_push',
    [
        'var value:Buffer=buffer_new(allocator,1); } buffer_push(value,1);',
        'var value:I64Vec=i64vec_new(allocator,1); } i64vec_push(value,1);',
        'var value:Vec<i64>=vec_new<i64>(allocator,1); } vec_push<i64>(value,1);',
    ],
)
def test_growable_container_push_requires_allocate_capability(declaration_and_push):
    source=f'''module push_capability
capability allocate;
fn main()->i32 {{ with capability allocate {{ let allocator:Allocator=system_allocator(); {declaration_and_push} return 0; }}'''
    with pytest.raises(CompileError,match='M2003: call to .*push.* requires capabilities'):
        Checker(parse(source)).check()


def test_push_operations_are_reported_as_allocation_hazards():
    program=parse('module push_audit\ncapability allocate;\nfn main()->i32 { return 0; }')
    operations={entry['operation'] for entry in capability_requirements(program) if entry['hazard']=='allocation'}
    assert {'buffer_push','i64vec_push','vec_push<T>'} <= operations
