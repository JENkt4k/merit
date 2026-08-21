from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"

CASES = (
    (
        "copy-nested-enum",
        "module demo\nenum Inner { Value(i64) }\nenum Outer { Value(Inner) }\n"
        "fn compute()->i64 { let x:Outer=0; return 0; }\n",
    ),
    (
        "owned-builtin-payload",
        "module demo\nenum Owned { Data(Buffer) }\n"
        "fn compute()->i64 { let x:Owned=0; return 0; }\n",
    ),
    (
        "owned-declared-payload",
        "module demo\nstruct Resource { value:i64; }\nenum Wrapped { Data(Resource) }\n"
        "fn compute()->i64 { let x:Wrapped=0; return 0; }\n",
    ),
    (
        "cyclic-payload",
        "module demo\nenum Cycle { Next(Cycle) }\n"
        "fn compute()->i64 { let x:Cycle=0; return 0; }\n",
    ),
)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _probe() -> str:
    calls = []
    for _, source in CASES:
        calls.append(f'classify("{_escape(source)}", allocator);')
    call_text = "\n        ".join(calls)
    return f'''module bootstrap_recursive_type_lifecycle_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_mir_source_ownership_metadata;
import bootstrap_mir_source_type_lifecycle;

capability allocate;

fn classify(source_text:String, allocator:Allocator)->i32
requires_caps [allocate]
{{
    let source:Buffer=buffer_from_string(allocator,source_text);
    let tokens:Vec<Token>=lex(source,allocator);
    let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
    let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
    var catalog:Vec<SourceTypeOwnershipEntry>=vec_new<SourceTypeOwnershipEntry>(allocator,4);
    let status:i32=derive_source_type_ownership_catalog(source,tokens,statements,operands,catalog);
    print(status);
    print(vec_len<SourceTypeOwnershipEntry>(catalog));
    if (status == 0) {{
        let entry:SourceTypeOwnershipEntry=vec_get<SourceTypeOwnershipEntry>(catalog,0);
        print(source_type_ownership_owned(entry));
    }}
    drop(catalog); drop(operands); drop(statements); drop(tokens); drop(source);
    return status;
}}

fn main()->i32 {{
    with capability allocate {{
        let allocator:Allocator=system_allocator();
        {call_text}
    }}
    return 0;
}}
'''


def _project(tmp_path: Path) -> tuple[Path, object]:
    root = tmp_path / "recursive_type_lifecycle"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "recursive_type_lifecycle_probe.mrt").write_text(_probe(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace(
        'entry = "src/lexer.mrt"',
        'entry = "src/recursive_type_lifecycle_probe.mrt"',
    )
    manifest.write_text(text, encoding="utf-8")
    return root, load_project(manifest)


def test_recursive_declared_payload_lifecycle_matches_interpreter_and_native(tmp_path: Path):
    root, project = _project(tmp_path)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    assert values == [
        0, 1, 0,  # nested Copy enum remains Copy
        0, 1, 1,  # Buffer payload makes enum owned
        0, 1, 1,  # declared struct payload makes enum owned
        2, 0,     # cyclic declared payload fails closed
    ]
