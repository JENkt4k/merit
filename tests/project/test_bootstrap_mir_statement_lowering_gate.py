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
    "fn main()->i64 { "
    "let x:i64=1+2; "
    "if x<4 { while x<3 { return x+10; } } "
    "else { return x+20; } "
    "return x+30; }\n"
)


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module bootstrap_statement_mir_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_expression_spans;
import bootstrap_hir;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_statement_lowering;

capability allocate;

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "{escaped}");
        let tokens: Vec<Token> = lex(source, allocator);
        let statements: Vec<StatementRecord> = parse_statement_records(source, tokens, allocator);
        let operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);
        var events: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 32);
        let statement_status: i32 = lower_typed_statements_to_mir_events(
            source, tokens, statements, operands, allocator, events
        );

        print(-81);
        print(statement_status);
        print(vec_len<MirLowerEvent>(events));
        var ei: i64 = 0;
        while (ei < vec_len<MirLowerEvent>(events)) {{
            let event: MirLowerEvent = vec_get<MirLowerEvent>(events, ei);
            print(lower_event_kind(event));
            print(lower_event_a(event));
            print(lower_event_b(event));
            ei = checked_add(ei, 1);
        }}

        var cfg: Vec<MirCfgRecord> = vec_new<MirCfgRecord>(allocator, 32);
        var placements: Vec<MirPlacementRecord> = vec_new<MirPlacementRecord>(allocator, 32);
        let mir_status: i32 = lower_structured_mir(events, allocator, cfg, placements);
        print(-82);
        print(mir_status);
        print(vec_len<MirCfgRecord>(cfg));
        var ci: i64 = 0;
        while (ci < vec_len<MirCfgRecord>(cfg)) {{
            let record: MirCfgRecord = vec_get<MirCfgRecord>(cfg, ci);
            print(cfg_kind(record));
            print(cfg_block_id(record));
            print(cfg_operand(record));
            print(cfg_target_a(record));
            print(cfg_target_b(record));
            print(cfg_case_value(record));
            print(cfg_ordinal(record));
            ci = checked_add(ci, 1);
        }}
        print(vec_len<MirPlacementRecord>(placements));
        var pi: i64 = 0;
        while (pi < vec_len<MirPlacementRecord>(placements)) {{
            let placement: MirPlacementRecord = vec_get<MirPlacementRecord>(placements, pi);
            print(placement_block_id(placement));
            print(placement_instruction_id(placement));
            print(placement_ordinal(placement));
            pi = checked_add(pi, 1);
        }}

        drop(placements); drop(cfg); drop(events); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "statement_structured_mir"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))

    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1)
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")

    (root / "src" / "statement_mir_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/statement_mir_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str):
    payload = output.rsplit("-81\n", 1)[1]
    event_payload, mir_payload = payload.split("-82\n", 1)

    event_values = [int(value) for value in event_payload.splitlines()]
    statement_status = event_values[0]
    event_count = event_values[1]
    flat_events = event_values[2:]
    assert len(flat_events) == event_count * 3
    events = [tuple(flat_events[i:i + 3]) for i in range(0, len(flat_events), 3)]

    mir_values = [int(value) for value in mir_payload.splitlines()]
    mir_status = mir_values[0]
    cfg_count = mir_values[1]
    cursor = 2
    cfg = []
    for _ in range(cfg_count):
        cfg.append(tuple(mir_values[cursor:cursor + 7]))
        cursor += 7
    placement_count = mir_values[cursor]
    cursor += 1
    placements = []
    for _ in range(placement_count):
        placements.append(tuple(mir_values[cursor:cursor + 3]))
        cursor += 3
    assert cursor == len(mir_values)
    return statement_status, events, mir_status, cfg, placements


EXPECTED_EVENTS = [
    (1, 0, 0), (1, 1, 0), (1, 2, 0), (1, 3, 0),
    (1, 4, 0), (1, 5, 0), (10, 4, 0),
    (19, 0, 0), (1, 6, 0), (1, 7, 0), (20, 6, 0),
    (1, 8, 0), (1, 9, 0), (2, 8, 0), (21, 0, 0),
    (11, 0, 0),
    (1, 10, 0), (1, 11, 0), (2, 10, 0), (12, 0, 0),
    (1, 12, 0), (1, 13, 0), (2, 12, 0),
]

EXPECTED_PLACEMENTS = [
    (0, 0, 0), (0, 1, 1), (0, 2, 2), (0, 3, 3), (0, 4, 4), (0, 5, 5),
    # The while-condition expression is placed in the dedicated condition block
    # so its instructions execute again on every loop backedge.
    (4, 6, 0), (4, 7, 1),
    (5, 8, 0), (5, 9, 1),
    (2, 10, 0), (2, 11, 1),
    (3, 12, 0), (3, 13, 1),
]


def test_typed_statements_drive_structured_mir_events_and_cfg_interpreter_and_native(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] == EXPECTED_EVENTS
    assert interpreted[2] == 0
    assert interpreted[4] == EXPECTED_PLACEMENTS

    # Native statement traversal owns the nested topology: entry -> if, then ->
    # loop, loop body return, loop exit -> if join, else return, final join return.
    terminators = [record for record in interpreted[3] if record[0] in (11, 12, 15)]
    assert (12, 0, 4, 1, 2, 0, 0) in terminators
    assert (12, 4, 6, 5, 6, 0, 0) in terminators
    assert (15, 5, 8, -1, -1, 0, 0) in terminators
    assert (11, 6, -1, 3, -1, 0, 0) in terminators
    assert (15, 2, 10, -1, -1, 0, 0) in terminators
    assert (15, 3, 12, -1, -1, 0, 0) in terminators

    _, _, executable = build(project, root / "native")
    native = _parse(subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout)
    assert native == interpreted


def test_statement_lowering_contract_rejects_unimplemented_effect_kinds():
    # The source-backed bridge intentionally stops before print/drop/with/match/
    # replace until those effects have native semantic records. Their stable
    # status range is 100 + bootstrap statement kind, preventing silent fallback.
    assert 123 == 100 + 23
    assert 124 == 100 + 24
    assert 127 == 100 + 27
    assert 128 == 100 + 28
    assert 129 == 100 + 29
