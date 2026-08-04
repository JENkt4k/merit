from pathlib import Path
import contextlib
import io
import subprocess

import pytest

from merit.compiler import CGenerator, Checker, CompileError, Interpreter, compile_file, mir, parse


LOCAL_REPLACE_PROGRAM = '''module replace_local
capability allocate;

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var current: Buffer = buffer_from_string(allocator, "old");
        let replacement: Buffer = buffer_from_string(allocator, "new-value");
        replace(current, replacement);
        print(current);
        drop(current);
    }
    return 0;
}'''


def checked(source=LOCAL_REPLACE_PROGRAM):
    program = parse(source)
    Checker(program).check()
    return program


def test_replace_owned_local_interpreter_and_native_match(tmp_path):
    program = checked()
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        assert Interpreter(program).run().value == 0

    source = tmp_path / "replace_local.mrt"
    executable = tmp_path / "replace_local"
    source.write_text(LOCAL_REPLACE_PROGRAM)
    compile_file(source, executable)
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert native.stdout == interpreted.getvalue() == "new-value\n"


def test_replace_lowers_rhs_once_before_drop_and_assignment():
    c_source = CGenerator(checked()).generate()
    replacement = next(line.strip() for line in c_source.splitlines() if "merit_Buffer _merit_replace_" in line)
    assert c_source.count(replacement) == 1
    suffix=replacement.split('_merit_replace_',1)[1].split(' ',1)[0]
    address = f"merit_Buffer *_merit_replace_address_{suffix} = &current;"
    assert c_source.count(address) == 1
    assert c_source.index(replacement) < c_source.index(address)
    drop=f"merit_buffer_drop(_merit_replace_address_{suffix});"
    assignment=f"*_merit_replace_address_{suffix} = _merit_replace_{suffix};"
    assert c_source.index(address) < c_source.index(drop) < c_source.index(assignment)


def test_replace_is_preserved_in_mir():
    function = mir(checked())["functions"][0]
    statements = function["semantic_blocks"][0]["statements"]
    capability = next(statement for statement in statements if statement["kind"] == "with_cap")
    capability_body = capability["operands"][1]
    assert any(statement["kind"] == "replace" for statement in capability_body)
    assert ["drop_implicit", "replacement"] not in statements


def test_replace_consumes_source():
    bad = LOCAL_REPLACE_PROGRAM.replace(
        "print(current);",
        "print(buffer_len(replacement));\n        print(current);",
    )
    with pytest.raises(CompileError, match="moved value replacement"):
        checked(bad)


def test_replace_rejects_immutable_target():
    bad = LOCAL_REPLACE_PROGRAM.replace("var current: Buffer", "let current: Buffer")
    with pytest.raises(CompileError, match="cannot assign to immutable binding current"):
        checked(bad)


def test_replace_rejects_self_replacement():
    bad = LOCAL_REPLACE_PROGRAM.replace("replace(current, replacement);", "replace(current, current);")
    with pytest.raises(CompileError, match="replacement source aliases target current"):
        checked(bad)


def test_replace_rejects_copy_storage():
    source = '''module replace_copy
fn main() -> i32 {
    var value: i64 = 1;
    replace(value, 2);
    return 0;
}'''
    with pytest.raises(CompileError, match="replace requires owned storage"):
        checked(source)


FIELD_REPLACE_PROGRAM = '''module replace_field
capability allocate;

struct OwnedText {
    data: Buffer;
}

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let initial: Buffer = buffer_from_string(allocator, "field-old");
        var text: OwnedText = OwnedText { data: initial };
        let replacement: Buffer = buffer_from_string(allocator, "field-new");
        replace(text.data, replacement);
        print(text.data);
        drop(text);
    }
    return 0;
}'''


def test_replace_owned_field_interpreter_and_native_match(tmp_path):
    program = checked(FIELD_REPLACE_PROGRAM)
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(program).run()

    source = tmp_path / "replace_field.mrt"
    executable = tmp_path / "replace_field"
    source.write_text(FIELD_REPLACE_PROGRAM)
    compile_file(source, executable)
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert native.stdout == interpreted.getvalue() == "field-new\n"


def test_replace_field_requires_mutable_aggregate():
    bad = FIELD_REPLACE_PROGRAM.replace("var text: OwnedText", "let text: OwnedText")
    with pytest.raises(CompileError, match="cannot assign to immutable binding text"):
        checked(bad)


def test_replace_field_rejects_aliasing_source():
    bad = FIELD_REPLACE_PROGRAM.replace("replace(text.data, replacement);", "replace(text.data, text.data);")
    with pytest.raises(CompileError, match="replacement source aliases target text.data"):
        checked(bad)


BORROWED_REPLACE_PROGRAM = '''module replace_borrowed
capability allocate;

fn update(borrow_mut target: Buffer, replacement: Buffer) -> void {
    replace(target, replacement);
}

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var current: Buffer = buffer_from_string(allocator, "borrow-old");
        let replacement: Buffer = buffer_from_string(allocator, "borrow-new");
        update(current, replacement);
        print(current);
        drop(current);
    }
    return 0;
}'''


def test_replace_through_mutable_borrow_interpreter_and_native_match(tmp_path):
    program = checked(BORROWED_REPLACE_PROGRAM)
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(program).run()

    source = tmp_path / "replace_borrowed.mrt"
    executable = tmp_path / "replace_borrowed"
    source.write_text(BORROWED_REPLACE_PROGRAM)
    compile_file(source, executable)
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert native.stdout == interpreted.getvalue() == "borrow-new\n"


VECTOR_REPLACE_PROGRAM = '''module replace_vector
capability allocate;

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var values: Vec<Buffer> = vec_new<Buffer>(allocator, 1);
        let initial: Buffer = buffer_from_string(allocator, "vector-old");
        vec_push<Buffer>(values, initial);
        let replacement: Buffer = buffer_from_string(allocator, "vector-new");
        vec_replace<Buffer>(values, 0, replacement);
        let result: Buffer = vec_pop<Buffer>(values);
        print(result);
        drop(result);
        drop(values);
    }
    return 0;
}'''


def test_replace_owned_vector_element_interpreter_and_native_match(tmp_path):
    program = checked(VECTOR_REPLACE_PROGRAM)
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(program).run()

    source = tmp_path / "replace_vector.mrt"
    executable = tmp_path / "replace_vector"
    source.write_text(VECTOR_REPLACE_PROGRAM)
    compile_file(source, executable)
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert native.stdout == interpreted.getvalue() == "vector-new\n"


def test_vec_replace_drops_old_element_before_assignment():
    c_source = CGenerator(checked(VECTOR_REPLACE_PROGRAM)).generate()
    helper = "merit_vec_replace__Buffer"
    start = c_source.index(helper)
    start = c_source.rfind("static ", 0, start)
    body = c_source[start:c_source.index("\n", start)]
    assert body.index("merit_buffer_drop(&v->data[i]);") < body.index("v->data[i]=x;")
    call=next(line.strip() for line in c_source.splitlines() if '(void)((merit_vec_replace__Buffer(' in line)
    arguments=call.split('merit_vec_replace__Buffer(',1)[1].split(')',1)[0].split(',')
    receiver_name=arguments[0].strip()
    receiver=next(line.strip() for line in c_source.splitlines() if f'*{receiver_name} = &values;' in line)
    index_name=arguments[1].strip()
    value_name=arguments[2].strip()
    index_line=f'int64_t {index_name} = 0;'
    value_line=f'merit_Buffer {value_name} = replacement;'
    assert c_source.index(receiver) < c_source.index(index_line) < c_source.index(value_line) < c_source.index(call)


def test_vec_replace_consumes_replacement_source():
    bad = VECTOR_REPLACE_PROGRAM.replace(
        "let result: Buffer",
        "print(buffer_len(replacement));\n        let result: Buffer",
    )
    with pytest.raises(CompileError, match="moved value replacement"):
        checked(bad)


def test_vec_replace_requires_mutable_vector():
    bad = VECTOR_REPLACE_PROGRAM.replace("var values: Vec<Buffer>", "let values: Vec<Buffer>")
    with pytest.raises(CompileError, match="borrow_mut argument values is not mutable"):
        checked(bad)


def test_vec_replace_rejects_copy_element_type():
    source = '''module replace_copy_vector
capability allocate;
fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var values: Vec<i64> = vec_new<i64>(allocator, 1);
        vec_push<i64>(values, 1);
        vec_replace<i64>(values, 0, 2);
        drop(values);
    }
    return 0;
}'''
    with pytest.raises(CompileError, match="requires an owned element type"):
        checked(source)


def test_vec_replace_rejects_source_aliasing_receiver():
    bad = VECTOR_REPLACE_PROGRAM.replace(
        "vec_replace<Buffer>(values, 0, replacement);",
        "vec_replace<Buffer>(values, 0, vec_pop<Buffer>(values));",
    )
    with pytest.raises(CompileError, match="replacement source aliases vector values"):
        checked(bad)
