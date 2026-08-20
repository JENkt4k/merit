from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
SOURCE = (
    "module demo\n"
    "enum Result { Ok(i64), Err(i64) }\n"
    "capability clock;\n"
    "fn main()->i64 { "
    "let r:Result=Ok(1); "
    "match (r) { Ok(value) => { with capability clock { return value; } } "
    "Err(code) => { return code; } } "
    "return 0; }\n"
)


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module bootstrap_statement_structure_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_structure;

capability allocate;

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "{escaped}");
        let tokens: Vec<Token> = lex(source, allocator);
        let statements: Vec<StatementRecord> = parse_statement_records(source, tokens, allocator);
        let operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);
        var arms: Vec<MatchArmRecord> = vec_new<MatchArmRecord>(allocator, 4);
        var scopes: Vec<CapabilityScopeRecord> = vec_new<CapabilityScopeRecord>(allocator, 4);
        let arm_status: i32 = lower_match_arm_records(source, tokens, statements, arms);
        let scope_status: i32 = lower_capability_scope_records(source, tokens, statements, operands, scopes);
        print(arm_status); print(scope_status);
        print(vec_len<MatchArmRecord>(arms));
        var ai: i64 = 0;
        while (ai < vec_len<MatchArmRecord>(arms)) {{
            let arm: MatchArmRecord = vec_get<MatchArmRecord>(arms, ai);
            print(match_arm_statement(arm));
            print(match_arm_subject_start(arm)); print(match_arm_subject_length(arm));
            print(match_arm_ordinal(arm));
            print(match_arm_variant_start(arm)); print(match_arm_variant_length(arm));
            print(match_arm_binding_start(arm)); print(match_arm_binding_length(arm));
            print(match_arm_body_start(arm)); print(match_arm_body_length(arm));
            ai = checked_add(ai, 1);
        }}
        print(vec_len<CapabilityScopeRecord>(scopes));
        var si: i64 = 0;
        while (si < vec_len<CapabilityScopeRecord>(scopes)) {{
            let scope: CapabilityScopeRecord = vec_get<CapabilityScopeRecord>(scopes, si);
            print(capability_scope_statement(scope)); print(capability_scope_ordinal(scope));
            print(capability_scope_name_start(scope)); print(capability_scope_name_length(scope));
            print(capability_scope_body_start(scope)); print(capability_scope_body_length(scope));
            si = checked_add(si, 1);
        }}
        drop(scopes); drop(arms); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "statement_structure"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "statement_structure_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/statement_structure_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str):
    values = [int(value) for value in output.splitlines()]
    assert values[0:2] == [0, 0]
    arm_count = values[2]
    cursor = 3
    arms = []
    for _ in range(arm_count):
        arms.append(tuple(values[cursor:cursor + 10]))
        cursor += 10
    scope_count = values[cursor]
    cursor += 1
    scopes = []
    for _ in range(scope_count):
        scopes.append(tuple(values[cursor:cursor + 6]))
        cursor += 6
    assert cursor == len(values)
    return arms, scopes


def _slice(start: int, length: int) -> str:
    return SOURCE[start:start + length]


def test_native_statement_structure_preserves_match_arms_and_capability_scopes(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    arms, scopes = interpreted

    assert len(arms) == 2
    assert [_slice(arm[1], arm[2]) for arm in arms] == ["r", "r"]
    assert [arm[3] for arm in arms] == [0, 1]
    assert [_slice(arm[4], arm[5]) for arm in arms] == ["Ok", "Err"]
    assert [_slice(arm[6], arm[7]) for arm in arms] == ["value", "code"]
    assert "with capability clock" in _slice(arms[0][8], arms[0][9])
    assert "return code" in _slice(arms[1][8], arms[1][9])

    assert len(scopes) == 1
    scope = scopes[0]
    assert scope[1] == 0
    assert _slice(scope[2], scope[3]) == "clock"
    assert "return value" in _slice(scope[4], scope[5])
    assert arms[0][8] <= scope[4] < arms[0][8] + arms[0][9]

    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _parse(native) == interpreted


def test_statement_structure_contract_is_not_encoded_in_flat_statement_operands():
    # The flat v1 statement contract identifies match/capability envelopes and
    # their subject/name operands, but arm identity, match subject span, and
    # lexical scope bodies are carried by structured records instead of being
    # rediscovered later by MIR adapters.
    statement_source = (PROJECT / "src" / "statements.mrt").read_text(encoding="utf-8")
    assert "Operand kinds: 1 binding name, 2 declared type, 3 expression, 4 capability name" in statement_source
    structure_source = (PROJECT / "src" / "statement_structure.mrt").read_text(encoding="utf-8")
    assert "struct MatchArmRecord" in structure_source
    assert "subject_start" in structure_source
    assert "subject_length" in structure_source
    assert "struct CapabilityScopeRecord" in structure_source
