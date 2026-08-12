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
    "var b:Resource=2; "
    "replace(b,a); "
    "return 0; }\n"
)


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module bootstrap_owned_source_replace_probe
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

fn print_event(borrow event: MirOwnershipEvent) -> i32 {{
    print(event.kind); print(event.a); print(event.b); return 0;
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

fn run_self_replace(allocator: Allocator) -> i32
requires_caps [allocate]
{{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 1);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 1));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 3);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_replace_binding(0, 0));
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 8);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 8);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}}

fn run_nonowned_source(allocator: Allocator) -> i32
requires_caps [allocate]
{{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 2);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 1));
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(1, 1, 0, 0));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 4);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(1));
    vec_push<MirOwnershipEvent>(input, ownership_event_replace_binding(0, 1));
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 8);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 8);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}}

fn main() -> i32 {{
    with capability allocate {{
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "{escaped}");
        let tokens: Vec<Token> = lex(source, allocator);
        let statements: Vec<StatementRecord> = parse_statement_records(source, tokens, allocator);
        let operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, allocator);
        var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 2);
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 0));
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(1, 1, 1, 1));

        var source_events: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 24);
        let source_status: i32 = lower_source_ownership_events(
            source, tokens, statements, operands, bindings, allocator, source_events
        );
        print(-111);
        print(source_status);
        print(vec_len<MirOwnershipEvent>(source_events));
        var si: i64 = 0;
        while (si < vec_len<MirOwnershipEvent>(source_events)) {{
            let event: MirOwnershipEvent = vec_get<MirOwnershipEvent>(source_events, si);
            print_event(event);
            si = checked_add(si, 1);
        }}

        var lowered: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 32);
        var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 16);
        let ownership_status: i32 = lower_ownership_flow(
            source_events, bindings, allocator, lowered, records
        );
        print(-112);
        print(ownership_status);
        print(validate_ownership_records(records, bindings));
        print(vec_len<MirOwnershipRecord>(records));
        var ri: i64 = 0;
        while (ri < vec_len<MirOwnershipRecord>(records)) {{
            let record: MirOwnershipRecord = vec_get<MirOwnershipRecord>(records, ri);
            print_record(record);
            ri = checked_add(ri, 1);
        }}

        var cfg: Vec<MirCfgRecord> = vec_new<MirCfgRecord>(allocator, 16);
        var placements: Vec<MirPlacementRecord> = vec_new<MirPlacementRecord>(allocator, 16);
        let cfg_status: i32 = lower_structured_mir(lowered, allocator, cfg, placements);
        print(-113);
        print(cfg_status);
        print(vec_len<MirPlacementRecord>(placements));
        var pi: i64 = 0;
        while (pi < vec_len<MirPlacementRecord>(placements)) {{
            let placement: MirPlacementRecord = vec_get<MirPlacementRecord>(placements, pi);
            print(placement_block_id(placement));
            print(placement_instruction_id(placement));
            print(placement_ordinal(placement));
            pi = checked_add(pi, 1);
        }}
        print(run_self_replace(allocator));
        print(run_nonowned_source(allocator));

        drop(placements); drop(cfg); drop(records); drop(lowered); drop(source_events);
        drop(bindings); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "owned_source_replace"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "owned_source_replace_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/owned_source_replace_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str):
    source_part, remainder = output.rsplit("-111\n", 1)[1].split("-112\n", 1)
    ownership_part, cfg_part = remainder.split("-113\n", 1)

    values = [int(value) for value in source_part.splitlines()]
    source_status = values[0]
    event_count = values[1]
    cursor = 2
    source_events = []
    for _ in range(event_count):
        source_events.append(tuple(values[cursor:cursor + 3]))
        cursor += 3
    assert cursor == len(values)

    values = [int(value) for value in ownership_part.splitlines()]
    ownership_status = values[0]
    validation_status = values[1]
    record_count = values[2]
    cursor = 3
    records = []
    for _ in range(record_count):
        records.append(tuple(values[cursor:cursor + 8]))
        cursor += 8
    assert cursor == len(values)

    values = [int(value) for value in cfg_part.splitlines()]
    cfg_status = values[0]
    placement_count = values[1]
    cursor = 2
    placements = []
    for _ in range(placement_count):
        placements.append(tuple(values[cursor:cursor + 3]))
        cursor += 3
    malformed = tuple(values[cursor:])
    return source_status, source_events, ownership_status, validation_status, records, cfg_status, placements, malformed


EXPECTED_RECORDS = [
    (1, -1, 0, -1, 0, 0, 0, 1),
    (1, -1, 1, -1, 1, 0, 0, 1),
    (4, 4, 1, -1, 1, 0, 1, 3),
    (5, 5, 1, 0, 0, 0, 3, 1),
    (7, 5, 0, 1, 0, 0, 1, 2),
    (6, 7, 1, -1, 1, 1, 1, 3),
]


def test_direct_owned_source_replace_preserves_both_binding_transitions(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    assert interpreted[0] == 0
    assert any(event[0] == 6 and event[1:] == (1, 0) for event in interpreted[1])
    assert interpreted[2] == 0
    assert interpreted[3] == 0
    assert interpreted[4] == EXPECTED_RECORDS
    assert interpreted[5] == 0
    assert [placement[1] for placement in interpreted[6]] == list(range(8))
    assert interpreted[7] == (69, 71)

    # The replacement target transition and source consumption describe one
    # move instruction, so they intentionally share instruction id 5.
    target = interpreted[4][3]
    source = interpreted[4][4]
    assert target[1] == source[1] == 5
    assert target[2:4] == (1, 0)
    assert source[2:4] == (0, 1)
    assert target[6:8] == (3, 1)
    assert source[6:8] == (1, 2)

    _, _, executable = build(project, root / "native")
    native = _parse(
        subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    )
    assert native == interpreted


def test_bilateral_replace_contract_rejects_alias_and_nonowned_source():
    assert EXPECTED_RECORDS[3][0] == 5
    assert EXPECTED_RECORDS[4][0] == 7
    assert (69, 71) == (69, 71)
