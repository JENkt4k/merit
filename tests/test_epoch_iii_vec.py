import contextlib
import io
import subprocess
from pathlib import Path

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, VEC_INTRINSICS, VECTOR_INTRINSIC_NAMES, compile_file, parse, vec_return_type
from merit.project.build import build, check, interpret
from merit.project.loader import load_project


VEC_I64_PROGRAM = r'''
module vec_i64_acceptance
capability allocate;

fn main() -> i32 {
    with capability allocate {
        let a: Allocator = system_allocator();
        var values: Vec<i64> = vec_new__i64(a, 2);
        vec_push__i64(values, 7);
        vec_push__i64(values, 11);
        vec_set__i64(values, 1, 13);
        print(vec_len__i64(values));
        print(vec_get__i64(values, 0));
        print(vec_pop__i64(values));
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
        var pairs: Vec<Pair<i64, i32>> = vec_new__Pair__i64__i32(a, 1);
        let p: Pair<i64, i32> = Pair<i64, i32> { first: 21, second: 5 };
        vec_push__Pair__i64__i32(pairs, p);
        let got: Pair<i64, i32> = vec_get__Pair__i64__i32(pairs, 0);
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
        var buffers: Vec<Buffer> = vec_new__Buffer(a, 2);
        let first: Buffer = buffer_from_string(a, "ab");
        let second: Buffer = buffer_from_string(a, "wxyz");
        vec_push__Buffer(buffers, first);
        vec_push__Buffer(buffers, second);
        print(vec_len__Buffer(buffers));
        let last: Buffer = vec_pop__Buffer(buffers);
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
        var texts: Vec<OwnedText> = vec_new__OwnedText(a, 2);
        let first_buffer: Buffer = buffer_from_string(a, "first");
        let second_buffer: Buffer = buffer_from_string(a, "second");
        let first: OwnedText = OwnedText { data: first_buffer };
        let second: OwnedText = OwnedText { data: second_buffer };
        vec_push__OwnedText(texts, first);
        vec_push__OwnedText(texts, second);
        print(vec_len__OwnedText(texts));
        let last: OwnedText = vec_pop__OwnedText(texts);
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

        var values: Vec<i64> = vec_new__i64(a, 2);
        vec_push__i64(values, 31);
        vec_push__i64(values, 32);
        let maybe: Option<Vec<i64>> = Option<Vec<i64>>::Some(values);
        match (maybe) {
            Option<Vec<i64>>::Some(inner) => {
                print(vec_len__i64(inner));
                print(vec_get__i64(inner, 1));
                drop(inner);
            }
            Option<Vec<i64>>::None => {
                print(0);
            }
        }

        var result_values: Vec<i64> = vec_new__i64(a, 1);
        vec_push__i64(result_values, 44);
        let outcome: Result<Vec<i64>, Error> = Result<Vec<i64>, Error>::Ok(result_values);
        match (outcome) {
            Result<Vec<i64>, Error>::Ok(ok_values) => {
                print(vec_get__i64(ok_values, 0));
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


def test_vec_generic_api_interpreter_and_native_agree(tmp_path):
    assert run_interpreter_and_native(VEC_GENERIC_API_PROGRAM, tmp_path, 'vec_generic_api') == '2\n8\n7\n'


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
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, data) == 0' in header
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, len) == sizeof(void *)' in header
    assert '_Static_assert(__builtin_offsetof(merit_Vec__OwnedText, cap) == sizeof(void *) + sizeof(size_t)' in header
    assert '_Static_assert(sizeof(merit_Vec__OwnedText) == sizeof(void *) + sizeof(size_t) * 2' in header


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
        'let got: Pair<i64, i32> = vec_get__Pair__i64__i32(pairs, 0);',
        'print(p.first);\n        let got: Pair<i64, i32> = vec_get__Pair__i64__i32(pairs, 0);',
    )
    with pytest.raises(CompileError, match='moved value p'):
        Checker(parse(bad)).check()


def test_vec_push_moves_buffer_value():
    bad = VEC_BUFFER_PROGRAM.replace(
        'print(vec_len__Buffer(buffers));',
        'print(buffer_len(first));\n        print(vec_len__Buffer(buffers));',
    )
    with pytest.raises(CompileError, match='moved value first'):
        Checker(parse(bad)).check()


def test_vec_get_rejects_owned_buffer_copy():
    bad = VEC_BUFFER_PROGRAM.replace(
        'let last: Buffer = vec_pop__Buffer(buffers);',
        'let last: Buffer = vec_get__Buffer(buffers, 0);',
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
        'let last: OwnedText = vec_pop__OwnedText(texts);',
        'let last: OwnedText = vec_get__OwnedText(texts, 0);',
    )
    with pytest.raises(CompileError, match='cannot copy owned element OwnedText'):
        Checker(parse(bad)).check()


def test_enum_constructor_moves_owned_payload_source():
    bad = ENUM_VEC_PROGRAM.replace(
        'match (maybe) {',
        'print(vec_len__i64(values));\n        match (maybe) {',
    )
    with pytest.raises(CompileError, match='moved value values'):
        Checker(parse(bad)).check()


def test_match_consumes_owned_enum_subject():
    bad = ENUM_VEC_PROGRAM.replace(
        'var result_values: Vec<i64> = vec_new__i64(a, 1);',
        'print(maybe);\n\n        var result_values: Vec<i64> = vec_new__i64(a, 1);',
    )
    with pytest.raises(CompileError, match='moved value maybe'):
        Checker(parse(bad)).check()


def test_generic_collections_project_interpreter_and_native(tmp_path):
    project = load_project(Path('examples/projects/generic_collections/Merit.toml'))
    check(project)
    output = interpret(project)
    _, _, executable = build(project, tmp_path / 'generic_collections')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert native == output == '2\n7\n13\n21\n5\n2\n4\n5\n2\n6\n2\n32\n44\n'
