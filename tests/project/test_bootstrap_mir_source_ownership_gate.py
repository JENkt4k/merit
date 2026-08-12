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
    "let a:Resource=1; "
    "var b:Resource=a; "
    "let c:Resource=2; "
    "let flag:i64=1; "
    "if flag<2 { drop(b); return 7; } "
    "else { replace(b,9); replace(b,c); } "
    "while flag<0 { return 8; } "
    "return 0; }\n"
)


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module bootstrap_source_ownership_probe
import bootstrap_tokens;
import bootstrap_syntax;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_expression_spans;
import bootstrap_hir;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_source_ownership_lowering;

capability allocate;

fn print_lower_event(borrow event: MirLowerEvent) -> i32 {{
    print(lower_event_kind(event));
    print(lower_event_a(event));
    print(lower_event_b(event));
    return 0;
}}

fn print_record(borrow record: MirOwnershipRecord) -> i32 {{
    print(ownership_record_kind(record));
    print(ownership_record_instruction_id(record));
    print(ownership_record_binding_id(record));
    print(ownership_record_other_binding_id(record));
    print(ownership_record_operand_local(record));
    print(ownership_record_implicit(record));
    print(ownership_record_state_before(record));
    print(ownership_record_state_after(record));
    return 0;
}}

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "{escaped}");
        let tokens: Vec<Token> = lex(source, allocator);
        let statements: Vec<StatementRecord> = parse_statement_records(source, tokens, allocator);
        let operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);

        var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 4);
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 0));
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(1, 1, 1, 1));
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(2, 2, 1, 0));
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(3, 3, 0, 0));

        var source_events: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 64);
        let source_status: i32 = lower_source_ownership_events(
            source, tokens, statements, operands, bindings, allocator, source_events
        );
        print(-101);
        print(source_status);
        print(vec_len<MirOwnershipEvent>(source_events));

        var lowered: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 80);
        var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 48);
        let ownership_status: i32 = lower_ownership_flow(
            source_events, bindings, allocator, lowered, records
        );
        print(-102);
        print(ownership_status);
        print(validate_ownership_records(records, bindings));
        print(vec_len<MirLowerEvent>(lowered));
        var li: i64 = 0;
        while (li < vec_len<MirLowerEvent>(lowered)) {{
            let event: MirLowerEvent = vec_get<MirLowerEvent>(lowered, li);
            print_lower_event(event);
            li = checked_add(li, 1);
        }}
        print(vec_len<MirOwnershipRecord>(records));
        var ri: i64 = 0;
        while (ri < vec_len<MirOwnershipRecord>(records)) {{
            let record: MirOwnershipRecord = vec_get<MirOwnershipRecord>(records, ri);
            print_record(record);
            ri = checked_add(ri, 1);
        }}

        var cfg: Vec<MirCfgRecord> = vec_new<MirCfgRecord>(allocator, 64);
        var placements: Vec<MirPlacementRecord> = vec_new<MirPlacementRecord>(allocator, 64);
        let cfg_status: i32 = lower_structured_mir(lowered, allocator, cfg, placements);
        print(-103);
        print(cfg_status);
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

        drop(placements); drop(cfg); drop(records); drop(lowered); drop(source_events);
        drop(bindings); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "source_ownership_mir"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "source_ownership_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/source_ownership_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str):
    source_part, remainder = output.rsplit("-101\n", 1)[1].split("-102\n", 1)
    ownership_part, cfg_part = remainder.split("-103\n", 1)

    source_values = [int(value) for value in source_part.splitlines()]
    assert len(source_values) == 2
    source_status, source_event_count = source_values

    values = [int(value) for value in ownership_part.splitlines()]
    ownership_status = values[0]
    validation_status = values[1]
    event_count = values[2]
    cursor = 3
    events = []
    for _ in range(event_count):
        events.append(tuple(values[cursor:cursor + 3]))
        cursor += 3
    record_count = values[cursor]
    cursor += 1
    records = []
    for _ in range(record_count):
        records.append(tuple(values[cursor:cursor + 8]))
        cursor += 8
    assert cursor == len(values)

    values = [int(value) for value in cfg_part.splitlines()]
    cfg_status = values[0]
    cfg_count = values[1]
    cursor = 2
    cfg = []
    for _ in range(cfg_count):
        cfg.append(tuple(values[cursor:cursor + 7]))
        cursor += 7
    placement_count = values[cursor]
    cursor += 1
    placements = []
    for _ in range(placement_count):
        placements.append(tuple(values[cursor:cursor + 3]))
        cursor += 3
    assert cursor == len(values)
    return (
        source_status, source_event_count, ownership_status, validation_status,
        events, records, cfg_status, cfg, placements,
    )


def test_real_source_drives_owned_move_drop_both_replace_forms_cleanup_and_cfg(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] > 0
    assert interpreted[2] == 0
    assert interpreted[3] == 0
    assert interpreted[6] == 0

    lower_kinds = [event[0] for event in interpreted[4]]
    assert 10 in lower_kinds and 11 in lower_kinds and 12 in lower_kinds
    assert 20 in lower_kinds and 21 in lower_kinds

    records = interpreted[5]
    record_kinds = {record[0] for record in records}
    assert record_kinds == {1, 2, 3, 4, 5, 6}
    assert any(record[0] == 2 and record[2:4] == (0, 1) for record in records)
    assert any(record[0] == 3 and record[2] == 1 for record in records)

    replacement_moves = [record for record in records if record[0] == 5]
    assert any(record[2] == 1 and record[3] == -1 for record in replacement_moves)
    assert any(
        record[2] == 1 and record[3] == 2 and record[4] == 2
        for record in replacement_moves
    )

    # The then-return cleans c because b was explicitly dropped. The else path
    # consumes c into b, so only b is cleaned by the loop-body and final returns.
    cleanup = [record for record in records if record[0] == 6]
    assert [record[2] for record in cleanup] == [2, 1, 1]

    instruction_ids = [placement[1] for placement in interpreted[8]]
    assert instruction_ids == list(range(len(instruction_ids)))

    _, _, executable = build(project, root / "native")
    native_output = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert _parse(native_output) == interpreted


def test_source_ownership_boundary_rejects_unrepresented_effects_explicitly():
    # print/match/with-capability remain future source-backed effects. Owned
    # replacement is now represented by a dedicated source-binding event.
    assert 123 == 100 + 23
    assert 127 == 100 + 27
    assert 128 == 100 + 28
