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
    "Left(x) => { } "
    "Right(y) => { with capability clock { } } "
    "} "
    "return 0; }\n"
)


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    left_decl = SOURCE.index("Left")
    right_decl = SOURCE.index("Right")
    clock_decl = SOURCE.index("clock")
    return f'''module bootstrap_resolved_control_flow_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_structure;
import bootstrap_statement_semantics;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_match_capability_flow;
import bootstrap_mir_resolved_control_flow;

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

        // The first arm terminates; the second survives with state 1. The
        // resolved-control bridge must exclude the terminated arm before CFG.
        var exits: Vec<MatchOwnershipExit> = vec_new<MatchOwnershipExit>(allocator, 2);
        vec_push<MatchOwnershipExit>(exits, match_exit(0, 0, 3, 1));
        vec_push<MatchOwnershipExit>(exits, match_exit(1, 0, 1, 0));
        var merged: Vec<i32> = vec_new<i32>(allocator, 1);
        var events: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 16);
        print(lower_resolved_match_control(resolved_arms, 1, exits, 4, merged, events));
        print(vec_len<i32>(merged));
        print(vec_get<i32>(merged, 0));
        print(vec_len<MirLowerEvent>(events));
        var ei: i64 = 0;
        while (ei < vec_len<MirLowerEvent>(events)) {{
            let event: MirLowerEvent = vec_get<MirLowerEvent>(events, ei);
            print(lower_event_kind(event));
            print(lower_event_a(event));
            print(lower_event_b(event));
            ei = checked_add(ei, 1);
        }}
        vec_push<MirLowerEvent>(events, mir_event_return(9));

        var cfg: Vec<MirCfgRecord> = vec_new<MirCfgRecord>(allocator, 32);
        var placements: Vec<MirPlacementRecord> = vec_new<MirPlacementRecord>(allocator, 4);
        print(lower_structured_mir(events, allocator, cfg, placements));
        print(vec_len<MirCfgRecord>(cfg));
        var ci: i64 = 0;
        while (ci < vec_len<MirCfgRecord>(cfg)) {{
            let record: MirCfgRecord = vec_get<MirCfgRecord>(cfg, ci);
            print(cfg_kind(record));
            print(cfg_block_id(record));
            print(cfg_operand(record));
            print(cfg_target_a(record));
            print(cfg_case_value(record));
            print(cfg_ordinal(record));
            ci = checked_add(ci, 1);
        }}

        var effects: Vec<MirCapabilityEffect> = vec_new<MirCapabilityEffect>(allocator, 4);
        print(lower_resolved_capability_control(resolved_scopes, effects));
        print(vec_len<MirCapabilityEffect>(effects));
        var fi: i64 = 0;
        while (fi < vec_len<MirCapabilityEffect>(effects)) {{
            let effect: MirCapabilityEffect = vec_get<MirCapabilityEffect>(effects, fi);
            print(capability_effect_kind(effect));
            print(capability_effect_id(effect));
            print(capability_effect_statement(effect));
            print(capability_effect_ordinal(effect));
            fi = checked_add(fi, 1);
        }}

        drop(effects); drop(placements); drop(cfg); drop(events); drop(merged); drop(exits);
        drop(resolved_scopes); drop(resolved_arms); drop(capability_catalog); drop(variants);
        drop(scopes); drop(arms); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "resolved_control_flow"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "resolved_control_flow_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/resolved_control_flow_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str) -> list[int]:
    return [int(value) for value in output.splitlines()]


def test_source_backed_resolved_match_and_capability_flow_reaches_structured_mir(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))

    # Structural + semantic resolution succeeded.
    assert interpreted[:4] == [0, 0, 0, 0]
    cursor = 4

    # Ownership merge succeeded and selected the sole surviving state.
    assert interpreted[cursor:cursor + 4] == [0, 1, 1, 6]
    cursor += 4

    # Typed two-arm enum match becomes two semantic cases plus a defensive
    # default/unreachable edge, then end_match.
    event_values = interpreted[cursor:cursor + 18]
    cursor += 18
    events = [tuple(event_values[i:i + 3]) for i in range(0, len(event_values), 3)]
    assert events == [
        (30, 4, 3),
        (31, 0, 0),
        (31, 1, 0),
        (32, 0, 0),
        (3, 0, 0),
        (33, 0, 0),
    ]

    # Structured MIR accepts the exhaustive match and contains a real
    # unreachable terminator for the impossible representation fallback.
    assert interpreted[cursor] == 0
    cfg_count = interpreted[cursor + 1]
    cursor += 2
    cfg_values = interpreted[cursor:cursor + cfg_count * 6]
    cursor += cfg_count * 6
    cfg = [tuple(cfg_values[i:i + 6]) for i in range(0, len(cfg_values), 6)]
    assert any(record[0] == 13 and record[4] == 0 for record in cfg)
    assert any(record[0] == 13 and record[4] == 1 for record in cfg)
    assert any(record[0] == 14 for record in cfg)
    assert any(record[0] == 16 for record in cfg)
    assert any(record[0] == 15 and record[2] == 9 for record in cfg)

    # Capability identity survives as paired enter/exit semantic effects.
    assert interpreted[cursor:cursor + 2] == [0, 2]
    cursor += 2
    first = tuple(interpreted[cursor:cursor + 4])
    second = tuple(interpreted[cursor + 4:cursor + 8])
    cursor += 8
    assert first[0:2] == (1, 9)
    assert second[0:2] == (2, 9)
    assert first[2] == second[2] and first[2] >= 0
    assert first[3] == second[3] == 0
    assert cursor == len(interpreted)

    _, _, executable = build(project, root / "native")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert _parse(native_output) == interpreted
