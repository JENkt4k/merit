from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


CASES = [
    ("integer-precedence", "1+2*3", 0),
    ("grouped-precedence", "(1+2)*3", 0),
    ("call", "f(1,2+3)", 0),
    ("constructor-field", "Point { x:1, y:2+3 }.x", 0),
    ("empty", "", 2),
    ("missing-rhs", "1+", 2),
    ("unexpected-leading-punctuation", ")", 2),
    ("malformed-call-argument", "f(,)", 2),
    ("trailing-token", "1 2", 3),
    ("missing-group-close", "(1+2", 3),
    ("missing-call-close", "f(1,2", 3),
    ("missing-constructor-close", "Point { x:1", 3),
]


def _probe_source(expression: str) -> str:
    return f'''module bootstrap_expression_validity_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_expression_validity;

capability allocate;

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, {json.dumps(expression)});
        let tokens: Vec<Token> = lex(source, allocator);
        let result: i32 = validate_expression_span_parse(source, tokens, 0, buffer_len(source), allocator);
        print(result);
        drop(tokens);
        drop(source);
    }}
    return 0;
}}
'''


def _promote_probe_to_entry(project_root: Path) -> Path:
    # The copied bootstrap fixture already has a main in lexer.mrt. A temporary
    # probe can become the project entry only if the fixture main is no longer
    # named main; keep the rest of bootstrap_lexer_core byte-for-byte intact so
    # the probe still exercises the real public lexer/expression implementation.
    lexer_path = project_root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    marker = "fn main() -> i32 {"
    assert lexer.count(marker) == 1
    lexer_path.write_text(
        lexer.replace(marker, "fn bootstrap_fixture_main() -> i32 {", 1),
        encoding="utf-8",
    )

    manifest = project_root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/validity_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return manifest


def _project_with_probe(tmp_path: Path, expression: str):
    project_root = tmp_path / "bootstrap_expression_validity"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    probe_path = project_root / "src/validity_probe.mrt"
    probe_path.write_text(_probe_source(expression), encoding="utf-8")
    manifest = _promote_probe_to_entry(project_root)
    return load_project(manifest), project_root


@pytest.mark.parametrize("case_id,expression,expected", CASES, ids=[case[0] for case in CASES])
def test_expression_validity_is_deterministic_in_interpreter_and_native(
    tmp_path, case_id, expression, expected
):
    project, project_root = _project_with_probe(tmp_path, expression)

    interpreted = int(interpret(project).strip())
    assert interpreted == expected

    _, _, executable = build(project, project_root / "expression_validity")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    native = int(native_output.strip())
    assert native == expected
    assert native == interpreted


def test_expression_validity_rejects_invalid_requested_span(tmp_path):
    project_root = tmp_path / "bootstrap_expression_validity_invalid_span"
    shutil.copytree(PROJECT, project_root, ignore=shutil.ignore_patterns("build"))
    probe = '''module bootstrap_expression_validity_invalid_span_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_expression_validity;

capability allocate;

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "1+2");
        let tokens: Vec<Token> = lex(source, allocator);
        print(validate_expression_span_parse(source, tokens, -1, 3, allocator));
        print(validate_expression_span_parse(source, tokens, 0, -1, allocator));
        drop(tokens);
        drop(source);
    }
    return 0;
}
'''
    (project_root / "src/validity_probe.mrt").write_text(probe, encoding="utf-8")
    manifest = _promote_probe_to_entry(project_root)
    project = load_project(manifest)

    assert interpret(project) == "4\n4\n"
    _, _, executable = build(project, project_root / "invalid_span")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == "4\n4\n"
