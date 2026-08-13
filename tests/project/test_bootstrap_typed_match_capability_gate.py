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
    "enum Choice { Left(Resource), Right(Resource) }\n"
    "capability clock;\n"
    "fn main()->i64 { "
    "let flag:i64=1; "
    "match flag { "
    "Left(x) => { return 1; } "
    "Right(y) => { with capability clock { return 2; } } "
    "} "
    "return 0; }\n"
)


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    left_decl = SOURCE.index("Left")
    right_decl = SOURCE.index("Right")
    clock_decl = SOURCE.index("clock")
    return f'''module bootstrap_typed_match_capability_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_structure;
import bootstrap_statement_semantics;
import bootstrap_mir_match_capability_flow;

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
        print(lower_match_arm_records(source, tokens, statements, arms));
        print(lower_capability_scope_records(source, tokens, statements, operands, scopes));
        print(vec_len<MatchArmRecord>(arms));
        print(vec_len<CapabilityScopeRecord>(scopes));

        var variants: Vec<EnumVariantCatalogEntry> = vec_new<EnumVariantCatalogEntry>(allocator, 2);
        vec_push<EnumVariantCatalogEntry>(variants, EnumVariantCatalogEntry {{
            enum_id: 7, variant_id: 70, ordinal: 0,
            name_start: {left_decl}, name_length: 4, payload_owned: 1
        }});
        vec_push<EnumVariantCatalogEntry>(variants, EnumVariantCatalogEntry {{
            enum_id: 7, variant_id: 71, ordinal: 1,
            name_start: {right_decl}, name_length: 5, payload_owned: 1
        }});
        var capability_catalog: Vec<CapabilityCatalogEntry> = vec_new<CapabilityCatalogEntry>(allocator, 1);
        vec_push<CapabilityCatalogEntry>(capability_catalog, CapabilityCatalogEntry {{
            capability_id: 9, name_start: {clock_decl}, name_length: 5
        }});

        var resolved_arms: Vec<ResolvedMatchArm> = vec_new<ResolvedMatchArm>(allocator, 4);
        var resolved_scopes: Vec<ResolvedCapabilityScope> = vec_new<ResolvedCapabilityScope>(allocator, 2);
        print(resolve_match_arms(source, arms, variants, 7, resolved_arms));
        print(resolve_capability_scopes(source, scopes, capability_catalog, resolved_scopes));
        print(vec_len<ResolvedMatchArm>(resolved_arms));
        var ai: i64 = 0;
        while (ai < vec_len<ResolvedMatchArm>(resolved_arms)) {{
            let arm: ResolvedMatchArm = vec_get<ResolvedMatchArm>(resolved_arms, ai);
            print(resolved_match_ordinal(arm));
            print(resolved_match_enum_id(arm));
            print(resolved_match_variant_id(arm));
            print(resolved_match_variant_ordinal(arm));
            print(resolved_match_payload_owned(arm));
            ai = checked_add(ai, 1);
        }}
        print(vec_len<ResolvedCapabilityScope>(resolved_scopes));
        let resolved_scope: ResolvedCapabilityScope = vec_get<ResolvedCapabilityScope>(resolved_scopes, 0);
        print(resolved_capability_id(resolved_scope));

        // Arm 0 terminates after consuming binding 0; arm 1 survives. The
        // terminated arm is excluded, so the survivor defines the merge state.
        var exits: Vec<MatchOwnershipExit> = vec_new<MatchOwnershipExit>(allocator, 4);
        vec_push<MatchOwnershipExit>(exits, match_exit(0, 0, 2, 1));
        vec_push<MatchOwnershipExit>(exits, match_exit(0, 1, 3, 1));
        vec_push<MatchOwnershipExit>(exits, match_exit(1, 0, 1, 0));
        vec_push<MatchOwnershipExit>(exits, match_exit(1, 1, 3, 0));
        var merged: Vec<i32> = vec_new<i32>(allocator, 2);
        print(validate_match_ownership_merge(resolved_arms, 2, exits, merged));
        print(vec_len<i32>(merged));
        print(vec_get<i32>(merged, 0));
        print(vec_get<i32>(merged, 1));

        // Both paths survive with contradictory state for binding 0.
        var conflict: Vec<MatchOwnershipExit> = vec_new<MatchOwnershipExit>(allocator, 4);
        vec_push<MatchOwnershipExit>(conflict, match_exit(0, 0, 2, 0));
        vec_push<MatchOwnershipExit>(conflict, match_exit(0, 1, 3, 0));
        vec_push<MatchOwnershipExit>(conflict, match_exit(1, 0, 1, 0));
        vec_push<MatchOwnershipExit>(conflict, match_exit(1, 1, 3, 0));
        var rejected: Vec<i32> = vec_new<i32>(allocator, 2);
        print(validate_match_ownership_merge(resolved_arms, 2, conflict, rejected));

        var effects: Vec<MirCapabilityEffect> = vec_new<MirCapabilityEffect>(allocator, 4);
        print(lower_capability_effects(resolved_scopes, effects));
        print(vec_len<MirCapabilityEffect>(effects));
        var ei: i64 = 0;
        while (ei < vec_len<MirCapabilityEffect>(effects)) {{
            let effect: MirCapabilityEffect = vec_get<MirCapabilityEffect>(effects, ei);
            print(capability_effect_kind(effect));
            print(capability_effect_id(effect));
            print(capability_effect_ordinal(effect));
            ei = checked_add(ei, 1);
        }}

        drop(effects); drop(rejected); drop(conflict); drop(merged); drop(exits);
        drop(resolved_scopes); drop(resolved_arms); drop(capability_catalog); drop(variants);
        drop(scopes); drop(arms); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "typed_match_capability"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "typed_match_capability_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/typed_match_capability_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str) -> list[int]:
    return [int(value) for value in output.splitlines()]


def test_typed_match_identity_n_way_ownership_and_capability_effect_ir_are_native(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))

    # structure statuses/counts, semantic statuses/count
    assert interpreted[:7] == [0, 0, 2, 1, 0, 0, 2]
    cursor = 7
    assert interpreted[cursor:cursor + 10] == [
        0, 7, 70, 0, 1,
        1, 7, 71, 1, 1,
    ]
    cursor += 10
    assert interpreted[cursor:cursor + 2] == [1, 9]
    cursor += 2

    # Successful N-way ownership merge excludes the terminated first arm.
    assert interpreted[cursor:cursor + 4] == [0, 2, 1, 3]
    cursor += 4
    # Conflicting live paths are rejected with the stable merge mismatch code.
    assert interpreted[cursor] == 9
    cursor += 1

    # One resolved lexical scope becomes an explicit enter/exit effect pair.
    assert interpreted[cursor:cursor + 8] == [0, 2, 1, 9, 0, 2, 9, 0]
    cursor += 8
    assert cursor == len(interpreted)

    _, _, executable = build(project, root / "native")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert _parse(native_output) == interpreted
