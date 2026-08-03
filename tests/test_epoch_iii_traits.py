import contextlib
import io
import subprocess
from pathlib import Path

import pytest

from merit.compiler import Checker, CompileError, Interpreter, compile_file, parse
from merit.project.loader import ProjectError, load_project
from merit.project.build import build, check, interpret


TRAIT_PROGRAM = r'''
module trait_acceptance

trait Ordered {
    fn compare(left: Self, right: Self) -> i32;
    fn identity(value: Self) -> Self;
}

fn main() -> i32 {
    return 0;
}
'''

IMPL_PROGRAM = r'''
module impl_acceptance

stable("v1") struct Point {
    x: i32;
}

trait Summarized {
    fn score(value: Self) -> i32;
}

impl Summarized for Point {
    fn score(value: Point) -> i32 {
        return value.x;
    }
}

fn main() -> i32 {
    return 0;
}
'''

GENERIC_BOUND_PROGRAM = r'''
module user_trait_bound_acceptance

stable("v1") struct Point {
    x: i32;
}

trait Summarized {
    fn score(value: Self) -> i32;
}

impl Summarized for Point {
    fn score(value: Point) -> i32 {
        return value.x;
    }
}

fn preserve<T: Summarized>(value: T) -> T {
    return value;
}

fn main() -> i32 {
    let p: Point = Point { x: 9 };
    let q: Point = preserve<Point>(p);
    print(q.x);
    return 0;
}
'''

GENERIC_TRAIT_CALL_PROGRAM = r'''
module user_trait_dispatch_acceptance

stable("v1") struct Point {
    x: i32;
}

trait Summarized {
    fn score(value: Self) -> i32;
}

impl Summarized for Point {
    fn score(value: Point) -> i32 {
        return value.x;
    }
}

fn summarize<T: Summarized>(value: T) -> i32 {
    return score(value);
}

fn main() -> i32 {
    let p: Point = Point { x: 17 };
    let total: i32 = summarize<Point>(p);
    print(total);
    return 0;
}
'''


def test_trait_declaration_check_accepts_self_signatures():
    program = parse(TRAIT_PROGRAM)
    Checker(program).check()
    trait = program.traits['Ordered']
    assert [method.name for method in trait.methods] == ['compare', 'identity']
    assert trait.methods[0].params[0] == ('left', 'Self', 'value')
    assert trait.methods[1].return_type == 'Self'


def test_duplicate_trait_method_is_rejected():
    bad = TRAIT_PROGRAM.replace(
        'fn identity(value: Self) -> Self;',
        'fn compare(value: Self) -> Self;',
    )
    with pytest.raises(CompileError, match='duplicate method compare'):
        Checker(parse(bad)).check()


def test_trait_method_unknown_type_is_rejected():
    bad = TRAIT_PROGRAM.replace('right: Self', 'right: Missing')
    with pytest.raises(CompileError, match='unknown type Missing'):
        Checker(parse(bad)).check()


def test_public_trait_survives_project_merge(tmp_path):
    project = tmp_path / 'trait_project'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "trait_project"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'traits.mrt').write_text(
        'module traits\n'
        'pub trait Described {\n'
        '    fn describe(value: Self) -> String;\n'
        '}\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'import traits;\n'
        'fn main() -> i32 { return 0; }\n'
    )

    loaded = load_project(project / 'Merit.toml')
    check(loaded)
    assert 'Described' in loaded.program.traits


def test_trait_bounds_acceptance_project_interpreter_and_native(tmp_path):
    project = load_project(Path('examples/projects/trait_bounds/Merit.toml'))
    check(project)
    assert any(function['name'] == 'summarize__Point' for function in project.program.functions)
    assert any(function['name'] == 'impl__Summarized__Point__score' for function in project.program.functions)
    interpreted = interpret(project)
    _, _, executable = build(project, tmp_path / 'trait_bounds')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted == native == '17\n'


def test_project_wide_generic_expansion_across_modules(tmp_path):
    project = tmp_path / 'project_wide_generics'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "project_wide_generics"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'types.mrt').write_text(
        'module types\n'
        'pub struct Box<T> { value: T; }\n'
        'pub fn unwrap<T>(box: Box<T>) -> T { return box.value; }\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'import types;\n'
        'fn main() -> i32 {\n'
        '    let box: Box<i32> = Box<i32> { value: 41 };\n'
        '    print(unwrap<i32>(box));\n'
        '    return 0;\n'
        '}\n'
    )

    loaded = load_project(project / 'Merit.toml')
    check(loaded)
    assert any(function['name'] == 'unwrap__i32' for function in loaded.program.functions)
    assert 'Box__i32' in loaded.program.structs
    interpreted = interpret(loaded)
    _, _, executable = build(loaded, tmp_path / 'project_wide_generics_bin')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted == native == '41\n'


def test_project_wide_trait_evidence_across_modules(tmp_path):
    project = tmp_path / 'project_wide_trait_evidence'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "project_wide_trait_evidence"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'domain.mrt').write_text(
        'module domain\n'
        'pub stable("v1") struct Point { x: i32; }\n'
        'pub trait Summarized { fn score(value: Self) -> i32; }\n'
        'impl Summarized for Point { fn score(value: Point) -> i32 { return value.x; } }\n'
    )
    (project / 'src' / 'algorithms.mrt').write_text(
        'module algorithms\n'
        'import domain;\n'
        'pub fn summarize<T: Summarized>(value: T) -> i32 { return score(value); }\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'import domain;\n'
        'import algorithms;\n'
        'fn main() -> i32 {\n'
        '    let p: Point = Point { x: 29 };\n'
        '    print(summarize<Point>(p));\n'
        '    return 0;\n'
        '}\n'
    )

    loaded = load_project(project / 'Merit.toml')
    check(loaded)
    assert any(function['name'] == 'summarize__Point' for function in loaded.program.functions)
    assert any(function['name'] == 'impl__Summarized__Point__score' for function in loaded.program.functions)
    interpreted = interpret(loaded)
    _, _, executable = build(loaded, tmp_path / 'project_wide_trait_evidence_bin')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted == native == '29\n'


def test_project_wide_generic_visibility_rejects_private_template(tmp_path):
    project = tmp_path / 'private_project_wide_generics'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "private_project_wide_generics"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'types.mrt').write_text(
        'module types\n'
        'struct Box<T> { value: T; }\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'import types;\n'
        'fn main() -> i32 {\n'
        '    let box: Box<i32> = Box<i32> { value: 1 };\n'
        '    return 0;\n'
        '}\n'
    )

    with pytest.raises(ProjectError, match='private symbol Box'):
        load_project(project / 'Merit.toml')


def test_project_wide_generic_bound_requires_imported_trait(tmp_path):
    project = tmp_path / 'generic_bound_missing_import'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "generic_bound_missing_import"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'domain.mrt').write_text(
        'module domain\n'
        'pub trait Summarized { fn score(value: Self) -> i32; }\n'
    )
    (project / 'src' / 'algorithms.mrt').write_text(
        'module algorithms\n'
        'pub fn summarize<T: Summarized>(value: T) -> i32 { return 0; }\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'import algorithms;\n'
        'fn main() -> i32 { return 0; }\n'
    )

    with pytest.raises(ProjectError, match='unimported module domain'):
        load_project(project / 'Merit.toml')


def test_project_wide_impl_rejects_private_trait(tmp_path):
    project = tmp_path / 'private_impl_trait'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "private_impl_trait"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'domain.mrt').write_text(
        'module domain\n'
        'stable("v1") struct Point { x: i32; }\n'
        'trait Hidden { fn score(value: Self) -> i32; }\n'
    )
    (project / 'src' / 'impls.mrt').write_text(
        'module impls\n'
        'import domain;\n'
        'impl Hidden for Point { fn score(value: Point) -> i32 { return value.x; } }\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'fn main() -> i32 { return 0; }\n'
    )

    with pytest.raises(ProjectError, match='private symbol Hidden'):
        load_project(project / 'Merit.toml')


def test_impl_declaration_check_accepts_matching_signature():
    program = parse(IMPL_PROGRAM)
    Checker(program).check()
    assert len(program.impls) == 1
    assert program.impls[0].trait_name == 'Summarized'
    assert program.impls[0].target_type == 'Point'


def test_impl_unknown_trait_is_rejected():
    bad = IMPL_PROGRAM.replace('impl Summarized for Point', 'impl Missing for Point')
    with pytest.raises(CompileError, match='unknown trait Missing'):
        Checker(parse(bad)).check()


def test_duplicate_impl_is_rejected():
    bad = IMPL_PROGRAM.replace(
        'fn main() -> i32',
        'impl Summarized for Point {\n'
        '    fn score(value: Point) -> i32 { return value.x; }\n'
        '}\n\n'
        'fn main() -> i32',
    )
    with pytest.raises(CompileError, match='duplicate impl Summarized for Point'):
        Checker(parse(bad)).check()


def test_impl_missing_trait_method_is_rejected():
    bad = IMPL_PROGRAM.replace('fn score(value: Point) -> i32', 'fn other(value: Point) -> i32')
    with pytest.raises(CompileError, match='does not match trait methods'):
        Checker(parse(bad)).check()


def test_impl_signature_mismatch_is_rejected():
    bad = IMPL_PROGRAM.replace('fn score(value: Point) -> i32', 'fn score(value: Point) -> i64')
    with pytest.raises(CompileError, match='does not match trait Summarized signature'):
        Checker(parse(bad)).check()


def test_impl_method_effects_are_rejected_until_trait_signatures_support_them():
    bad = IMPL_PROGRAM.replace(
        'fn score(value: Point) -> i32 {',
        'fn score(value: Point) -> i32 effects [io] {',
    )
    with pytest.raises(CompileError, match='cannot declare effects or capabilities'):
        Checker(parse(bad)).check()


def test_duplicate_impl_across_project_modules_is_rejected(tmp_path):
    project = tmp_path / 'duplicate_impl_project'
    (project / 'src').mkdir(parents=True)
    (project / 'Merit.toml').write_text(
        '[package]\n'
        'name = "duplicate_impl_project"\n'
        'entry = "src/main.mrt"\n'
        'sources = ["src/*.mrt"]\n'
    )
    (project / 'src' / 'traits.mrt').write_text(
        'module traits\n'
        'pub stable("v1") struct Point { x: i32; }\n'
        'pub trait Summarized { fn score(value: Self) -> i32; }\n'
        'impl Summarized for Point { fn score(value: Point) -> i32 { return value.x; } }\n'
    )
    (project / 'src' / 'main.mrt').write_text(
        'module main\n'
        'import traits;\n'
        'impl Summarized for Point { fn score(value: Point) -> i32 { return value.x; } }\n'
        'fn main() -> i32 { return 0; }\n'
    )

    loaded = load_project(project / 'Merit.toml')
    with pytest.raises(CompileError, match='duplicate impl Summarized for Point'):
        check(loaded)


def test_generic_bound_uses_user_defined_impl_registry():
    program = parse(GENERIC_BOUND_PROGRAM)
    Checker(program).check()
    assert any(function['name'] == 'preserve__Point' for function in program.functions)


def test_generic_bound_rejects_missing_user_defined_impl():
    bad = GENERIC_BOUND_PROGRAM.replace(
        'impl Summarized for Point {\n'
        '    fn score(value: Point) -> i32 {\n'
        '        return value.x;\n'
        '    }\n'
        '}\n\n',
        '',
    )
    with pytest.raises(CompileError, match='type Point does not satisfy generic bound Summarized'):
        parse(bad)


def test_user_trait_bound_interpreter_and_native_agree(tmp_path):
    source = tmp_path / 'user_trait_bound.mrt'
    source.write_text(GENERIC_BOUND_PROGRAM)
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(parse(GENERIC_BOUND_PROGRAM)).run()
    _, _, _, executable = compile_file(source, tmp_path / 'user_trait_bound')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted.getvalue() == native == '9\n'


def test_generic_user_trait_method_call_interpreter_and_native_agree(tmp_path):
    program = parse(GENERIC_TRAIT_CALL_PROGRAM)
    Checker(program).check()
    assert any(function['name'] == 'impl__Summarized__Point__score' for function in program.functions)
    assert any(function['name'] == 'summarize__Point' for function in program.functions)

    source = tmp_path / 'user_trait_call.mrt'
    source.write_text(GENERIC_TRAIT_CALL_PROGRAM)
    interpreted = io.StringIO()
    with contextlib.redirect_stdout(interpreted):
        Interpreter(parse(GENERIC_TRAIT_CALL_PROGRAM)).run()
    _, _, _, executable = compile_file(source, tmp_path / 'user_trait_call')
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert interpreted.getvalue() == native == '17\n'


def test_ambiguous_trait_method_name_in_generic_bounds_is_rejected():
    source = r'''
module ambiguous_trait_methods

stable("v1") struct Point { x: i32; }

trait Primary { fn score(value: Self) -> i32; }
trait Secondary { fn score(value: Self) -> i32; }

impl Primary for Point { fn score(value: Point) -> i32 { return value.x; } }
impl Secondary for Point { fn score(value: Point) -> i32 { return value.x; } }

fn summarize<T: Primary + Secondary>(value: T) -> i32 {
    return score(value);
}

fn main() -> i32 {
    let p: Point = Point { x: 1 };
    return summarize<Point>(p);
}
'''
    with pytest.raises(CompileError, match='ambiguous trait method score'):
        parse(source)
