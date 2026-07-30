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
