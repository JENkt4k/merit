import contextlib
import io
import subprocess
import tempfile
from pathlib import Path

import pytest

from merit.compiler import Checker, CompileError, Interpreter, compile_file, expand_generics, parse

PROGRAM = r'''
module generic_acceptance

struct Pair<T, U> {
    first: T;
    second: U;
}

enum Option<T> {
    Some(T),
    None
}

enum Result<T, E> {
    Ok(T),
    Err(E)
}

fn choose_max<T: Ord>(a: T, b: T) -> T {
    if (a >= b) { return a; } else { return b; }
}

fn identity<T: Copy>(value: T) -> T {
    return value;
}

fn main() -> i32 {
    let pair: Pair<i64, i32> = Pair<i64, i32> { first: 7, second: 3 };
    let best: i64 = choose_max<i64>(pair.first, 12);
    let copied: i64 = identity<i64>(best);
    let maybe: Option<i64> = Option<i64>::Some(copied);
    let outcome: Result<i64, i32> = Result<i64, i32>::Ok(copied);
    match (maybe) {
        Option<i64>::Some(value) => { print(value); }
        Option<i64>::None => { print(0); }
    }
    match (outcome) {
        Result<i64, i32>::Ok(value) => { print(value); }
        Result<i64, i32>::Err(error) => { print(error); }
    }
    return 0;
}
'''


def test_generic_struct_enum_and_function_check():
    program = parse(PROGRAM)
    Checker(program).check()
    assert 'Pair__i64__i32' in program.structs
    assert 'Option__i64' in program.enums
    assert 'Result__i64__i32' in program.enums
    assert any(f['name'] == 'choose_max__i64' for f in program.functions)


def test_generic_interpreter_and_native_agree(tmp_path: Path):
    source = tmp_path / 'generic.mrt'
    source.write_text(PROGRAM)
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(parse(PROGRAM)).run()
    _, _, _, executable = compile_file(source, tmp_path / 'generic')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted.getvalue() == native == '12\n12\n'


def test_generic_arity_is_checked():
    bad = PROGRAM.replace('Pair<i64, i32>', 'Pair<i64>')
    with pytest.raises(CompileError, match='expects 2 type arguments'):
        parse(bad)


def test_builtin_generic_bound_is_enforced():
    bad = PROGRAM.replace('identity<i64>(best)', 'identity<Buffer>(best)')
    with pytest.raises(CompileError, match='does not satisfy generic bound Copy'):
        parse(bad)


def test_generic_variant_names_are_nominally_scoped():
    expanded = expand_generics(PROGRAM)
    assert 'Option__i64__Some' in expanded
    assert 'Result__i64__i32__Ok' in expanded
