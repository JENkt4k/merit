import pytest

from merit.compiler import Checker, CompileError, parse
from merit.project.loader import load_project
from merit.project.build import check


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
