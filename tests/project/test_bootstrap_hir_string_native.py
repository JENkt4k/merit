from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"

PROBE = '''module bootstrap_hir_string_probe
import bootstrap_hir;
import bootstrap_hir_strings;

fn main() -> i32 {
    let node: HirExpressionRecord = lower_string_hir_record(0, 7, 6);
    print(validate_string_hir_record(node));
    print(hir_kind(node));
    print(hir_start(node));
    print(hir_length(node));
    print(hir_type_code(node));
    print(hir_numeric_policy(node));
    return 0;
}
'''


def _project(tmp_path: Path):
    root = tmp_path / "bootstrap_hir_string"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src/lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src/hir_string_probe.mrt").write_text(PROBE, encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/hir_string_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def test_string_hir_adapter_has_interpreter_and_native_parity(tmp_path):
    project, root = _project(tmp_path)
    expected = "0\n12\n0\n7\n6\n0\n"
    assert interpret(project) == expected
    _, _, executable = build(project, root / "hir_string")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == expected
