from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


def _probe_source() -> str:
    return r'''module bootstrap_ownership_flow_probe
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_ownership_flow;

capability allocate;

fn print_event(borrow event: MirLowerEvent) -> i32 {
    print(lower_event_kind(event));
    print(lower_event_a(event));
    print(lower_event_b(event));
    return 0;
}

fn print_record(borrow record: MirOwnershipRecord) -> i32 {
    print(ownership_record_kind(record));
    print(ownership_record_instruction_id(record));
    print(ownership_record_binding_id(record));
    print(ownership_record_other_binding_id(record));
    print(ownership_record_operand_local(record));
    print(ownership_record_implicit(record));
    print(ownership_record_state_before(record));
    print(ownership_record_state_after(record));
    return 0;
}

fn run_double_drop(allocator: Allocator) -> i32
requires_caps [allocate]
{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 1);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 1));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 4);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 8);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 8);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}

fn run_immutable_replace(allocator: Allocator) -> i32
requires_caps [allocate]
{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 1);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 0));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 3);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_replace(0, 7));
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 8);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 8);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}

fn run_branch_divergence(allocator: Allocator) -> i32
requires_caps [allocate]
{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 1);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 1));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 6);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_if(2));
    vec_push<MirOwnershipEvent>(input, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_end_if());
    vec_push<MirOwnershipEvent>(input, ownership_event_place(99));
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 12);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 8);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}

fn run_loop_divergence(allocator: Allocator) -> i32
requires_caps [allocate]
{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 1);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 1));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 6);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_begin_while());
    vec_push<MirOwnershipEvent>(input, ownership_event_while(2));
    vec_push<MirOwnershipEvent>(input, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_end_while());
    vec_push<MirOwnershipEvent>(input, ownership_event_place(99));
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 12);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 8);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 3);
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 0));
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(1, 1, 1, 1));
        vec_push<MirOwnershipBinding>(bindings, ownership_binding(2, 2, 1, 1));

        var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 24);
        vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
        vec_push<MirOwnershipEvent>(input, ownership_event_place(99));
        vec_push<MirOwnershipEvent>(input, ownership_event_move(0, 1));
        vec_push<MirOwnershipEvent>(input, ownership_event_activate(2));
        vec_push<MirOwnershipEvent>(input, ownership_event_if(9));
        vec_push<MirOwnershipEvent>(input, ownership_event_return(11));
        vec_push<MirOwnershipEvent>(input, ownership_event_else());
        vec_push<MirOwnershipEvent>(input, ownership_event_begin_while());
        vec_push<MirOwnershipEvent>(input, ownership_event_while(10));
        vec_push<MirOwnershipEvent>(input, ownership_event_place(55));
        vec_push<MirOwnershipEvent>(input, ownership_event_end_while());
        vec_push<MirOwnershipEvent>(input, ownership_event_drop(2));
        vec_push<MirOwnershipEvent>(input, ownership_event_replace(1, 12));
        vec_push<MirOwnershipEvent>(input, ownership_event_end_if());
        vec_push<MirOwnershipEvent>(input, ownership_event_return(13));

        var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 32);
        var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 24);
        let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);

        print(-91);
        print(status);
        print(vec_len<MirLowerEvent>(output));
        var event_index: i64 = 0;
        while (event_index < vec_len<MirLowerEvent>(output)) {
            let event: MirLowerEvent = vec_get<MirLowerEvent>(output, event_index);
            print_event(event);
            event_index = checked_add(event_index, 1);
        }
        print(vec_len<MirOwnershipRecord>(records));
        var record_index: i64 = 0;
        while (record_index < vec_len<MirOwnershipRecord>(records)) {
            let record: MirOwnershipRecord = vec_get<MirOwnershipRecord>(records, record_index);
            print_record(record);
            record_index = checked_add(record_index, 1);
        }

        var cfg: Vec<MirCfgRecord> = vec_new<MirCfgRecord>(allocator, 32);
        var placements: Vec<MirPlacementRecord> = vec_new<MirPlacementRecord>(allocator, 32);
        let cfg_status: i32 = lower_structured_mir(output, allocator, cfg, placements);
        print(-92);
        print(cfg_status);
        print(vec_len<MirPlacementRecord>(placements));
        var placement_index: i64 = 0;
        while (placement_index < vec_len<MirPlacementRecord>(placements)) {
            let placement: MirPlacementRecord = vec_get<MirPlacementRecord>(placements, placement_index);
            print(placement_block_id(placement));
            print(placement_instruction_id(placement));
            print(placement_ordinal(placement));
            placement_index = checked_add(placement_index, 1);
        }

        print(-93);
        print(run_double_drop(allocator));
        print(run_immutable_replace(allocator));
        print(run_branch_divergence(allocator));
        print(run_loop_divergence(allocator));

        drop(placements); drop(cfg); drop(records); drop(output); drop(input); drop(bindings);
    }
    return 0;
}
'''


def _project(tmp_path: Path):
    root = tmp_path / "ownership_flow"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1)
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "ownership_flow_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/ownership_flow_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str):
    first, remainder = output.rsplit("-91\n", 1)[1].split("-92\n", 1)
    second, third = remainder.split("-93\n", 1)
    values = [int(value) for value in first.splitlines()]
    status = values[0]
    event_count = values[1]
    cursor = 2
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

    cfg_values = [int(value) for value in second.splitlines()]
    cfg_status = cfg_values[0]
    placement_count = cfg_values[1]
    cursor = 2
    placements = []
    for _ in range(placement_count):
        placements.append(tuple(cfg_values[cursor:cursor + 3]))
        cursor += 3
    assert cursor == len(cfg_values)
    malformed = tuple(int(value) for value in third.splitlines())
    return status, events, records, cfg_status, placements, malformed


EXPECTED_EVENTS = [
    (1, 0, 0), (1, 1, 0), (10, 9, 0),
    (1, 2, 0), (1, 3, 0), (2, 11, 0),
    (11, 0, 0), (19, 0, 0), (20, 10, 0), (1, 4, 0), (21, 0, 0),
    (1, 5, 0), (1, 6, 0), (1, 7, 0), (12, 0, 0),
    (1, 8, 0), (2, 13, 0),
]

EXPECTED_RECORDS = [
    (1, -1, 0, -1, 0, 0, 0, 1),
    (2, 1, 0, 1, 0, 0, 1, 2),
    (1, -1, 2, -1, 2, 0, 0, 1),
    (6, 2, 2, -1, 2, 1, 1, 3),
    (6, 3, 1, -1, 1, 1, 1, 3),
    (3, 5, 2, -1, 2, 0, 1, 3),
    (4, 6, 1, -1, 1, 0, 1, 3),
    (5, 7, 1, -1, 12, 0, 3, 1),
    (6, 8, 1, -1, 1, 1, 1, 3),
]

EXPECTED_PLACEMENTS = [
    (0, 0, 0), (0, 1, 1),
    (1, 2, 0), (1, 3, 1),
    (5, 4, 0),
    (6, 5, 0), (6, 6, 1), (6, 7, 2),
    (3, 8, 0),
]


def test_native_ownership_flow_inserts_exact_cleanup_and_preserves_cfg(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] == EXPECTED_EVENTS
    assert interpreted[2] == EXPECTED_RECORDS
    assert interpreted[3] == 0
    assert interpreted[4] == EXPECTED_PLACEMENTS
    assert interpreted[5] == (34, 38, 61, 63)

    _, _, executable = build(project, root / "native")
    native_output = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    native = _parse(native_output)
    assert native == interpreted


def test_ownership_contract_covers_move_drop_replace_cleanup_and_flow_merges():
    assert {record[0] for record in EXPECTED_RECORDS} == {1, 2, 3, 4, 5, 6}
    cleanup_bindings = [record[2] for record in EXPECTED_RECORDS if record[0] == 6]
    assert cleanup_bindings == [2, 1, 1]
    # First return cleans the then path in reverse binding order; after restoring
    # the else entry state, explicit drop + replace leave destination live for
    # exactly one cleanup at the joined final return.
    assert [record[1] for record in EXPECTED_RECORDS if record[0] != 1] == [1, 2, 3, 5, 6, 7, 8]
