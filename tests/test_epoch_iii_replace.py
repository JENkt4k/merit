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
    replacement = "merit_Buffer _merit_replace_0 = replacement;"
    assert c_source.count(replacement) == 1
    assert c_source.index(replacement) < c_source.index("merit_buffer_drop(&current);")
    assert c_source.index("merit_buffer_drop(&current);") < c_source.index("current = _merit_replace_0;")


def test_replace_is_preserved_in_mir():
    function = mir(checked())["functions"][0]
    statements = function["blocks"][0]["statements"]
    capability_body = next(statement[2] for statement in statements if statement[0] == "with_cap")
    assert any(statement[0] == "replace" for statement in capability_body)
    assert ("drop_implicit", "replacement") not in statements


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
