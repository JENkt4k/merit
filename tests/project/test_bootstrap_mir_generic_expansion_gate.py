from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.compiler import Checker, parse
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples" / "projects" / "bootstrap_lexer"
SOURCE = """module demo
fn identity<T: Copy>(value:T)->T { return value; }
fn main()->i64 { return identity<i64>(7); }
"""
AGGREGATE_SOURCE = """module demo
struct Pair<T,U> { first:T; second:U; }
enum Option<T> { Some(T), None }
fn main()->i32 {
    let pair:Pair<i64,i32>=Pair<i64,i32>{first:7,second:3};
    let maybe:Option<i64>=Option<i64>::Some(pair.first);
    match(maybe){Option<i64>::Some(value)=>{print(value);} Option<i64>::None=>{print(0);}}
    return 0;
}
"""
MISSING_BOUND_SOURCE = """module demo
fn copy_value<T: Copy>(value:T)->T { return value; }
fn main()->i32 { with capability allocate {
    let allocator:Allocator=system_allocator();
    let value:Buffer=buffer_new(allocator,0);
    let copied:Buffer=copy_value<Buffer>(value);
    drop(copied);
} return 0; }
"""
TRAIT_DISPATCH_SOURCE = """module demo
struct Point { x:i32; }
trait Summarized { fn score(value:Self)->i32; }
impl Summarized for Point { fn score(value:Point)->i32 { return value.x; } }
fn summarize<T:Summarized>(value:T)->i32 { return score(value); }
fn main()->i32 {
    let point:Point=Point{x:17};
    let total:i32=summarize<Point>(point);
    print(total);return 0;
}
"""
VEC_I64_SOURCE = """module demo
capability allocate;
fn main()->i32 { with capability allocate {
    let allocator:Allocator=system_allocator();
    var values:Vec<i64>=vec_new<i64>(allocator,2);
    vec_push<i64>(values,7);vec_push<i64>(values,11);
    print(vec_len<i64>(values));print(vec_get<i64>(values,0));print(vec_pop<i64>(values));
} return 0; }
"""


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _probe(source_text: str) -> str:
    return f'''module bootstrap_mir_generic_expansion_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_mir_generic_expansion;

capability allocate;

fn main()->i32 {{
    with capability allocate {{
        let allocator:Allocator=system_allocator();
        let source:Buffer=buffer_from_string(allocator,"{_escape(source_text)}");
        let tokens:Vec<Token>=lex(source,allocator);
        var output:Buffer=buffer_new(allocator,buffer_len(source));
        let status:i32=expand_generic_source(source,tokens,allocator,output);
        print(status);print(buffer_len(output));
        var index:i64=0;
        while(index<buffer_len(output)){{print(buffer_get(output,index));index=checked_add(index,1);}}
        drop(output);drop(tokens);drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path, source_text: str = SOURCE):
    root = tmp_path / "generic_expansion"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer_path.read_text(encoding="utf-8"), count=1,
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "generic_expansion_probe.mrt").write_text(_probe(source_text), encoding="utf-8")
    manifest = root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'entry = "src/lexer.mrt"', 'entry = "src/generic_expansion_probe.mrt"'
        ), encoding="utf-8",
    )
    return root, load_project(manifest)


def test_native_generic_function_expansion_is_concrete_before_mir(tmp_path: Path):
    root, project = _project(tmp_path)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    assert values[1] == len(values) - 2
    expanded = bytes(values[2:]).decode("utf-8")
    assert "fn identity__i64(value:i64)->i64" in expanded
    assert "return identity__i64(7);" in expanded
    assert "fn identity<T" not in expanded
    Checker(parse(expanded)).check()


def test_native_generic_struct_and_enum_expansion_is_nominally_scoped(tmp_path: Path):
    root, project = _project(tmp_path, AGGREGATE_SOURCE)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    expanded = bytes(values[2:]).decode("utf-8")
    assert values[0] == 0, expanded
    assert "struct Pair__i64__i32" in expanded
    assert "enum Option__i64" in expanded
    assert "Option__i64__Some(i64)" in expanded
    assert "Option__i64__None" in expanded
    assert "Pair<i64" not in expanded
    assert "Option<i64>" not in expanded
    Checker(parse(expanded)).check()


def test_native_generic_expansion_fails_closed_for_missing_bound(tmp_path: Path):
    root, project = _project(tmp_path, MISSING_BOUND_SOURCE)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[:2] == [205, 0]


def test_native_generic_expansion_emits_static_user_trait_dispatch(tmp_path: Path):
    root, project = _project(tmp_path, TRAIT_DISPATCH_SOURCE)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    expanded = bytes(values[2:]).decode("utf-8")
    assert values[0] == 0, expanded
    assert "fn impl__Summarized__Point__score(value:Point)->i32" in expanded
    assert "fn summarize__Point(value:Point)->i32" in expanded
    assert "return impl__Summarized__Point__score(value);" in expanded
    Checker(parse(expanded)).check()


def test_native_generic_expansion_concretizes_builtin_vec_surface(tmp_path: Path):
    root, project = _project(tmp_path, VEC_I64_SOURCE)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    expanded = bytes(values[2:]).decode("utf-8")
    assert values[0] == 0, expanded
    assert "Vec__i64" in expanded
    assert "vec_new__i64" in expanded
    assert "vec_push__i64" in expanded
    assert "vec_pop__i64" in expanded
    Checker(parse(expanded)).check()
