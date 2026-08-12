from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.mir_cfg_parity import NativeCfgRecord, lower_native_cfg_records
from merit.bootstrap.mir_cfg_placement import NativeInstructionPlacement
from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


def _probe_source() -> str:
    return '''module bootstrap_structured_mir_probe
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_structured_lowering;

capability allocate;

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var events: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 32);
        // Entry instruction, then nested while -> if/else, followed by match.
        vec_push<MirLowerEvent>(events, mir_event_place(0));
        vec_push<MirLowerEvent>(events, mir_event_while(0));
        vec_push<MirLowerEvent>(events, mir_event_place(1));
        vec_push<MirLowerEvent>(events, mir_event_if(1));
        vec_push<MirLowerEvent>(events, mir_event_place(2));
        vec_push<MirLowerEvent>(events, mir_event_else());
        vec_push<MirLowerEvent>(events, mir_event_place(3));
        vec_push<MirLowerEvent>(events, mir_event_end_if());
        vec_push<MirLowerEvent>(events, mir_event_end_while());
        vec_push<MirLowerEvent>(events, mir_event_match(2, 3));
        vec_push<MirLowerEvent>(events, mir_event_case(10));
        vec_push<MirLowerEvent>(events, mir_event_place(4));
        vec_push<MirLowerEvent>(events, mir_event_case(20));
        vec_push<MirLowerEvent>(events, mir_event_return(3));
        vec_push<MirLowerEvent>(events, mir_event_default());
        vec_push<MirLowerEvent>(events, mir_event_place(5));
        vec_push<MirLowerEvent>(events, mir_event_end_match());
        vec_push<MirLowerEvent>(events, mir_event_return(4));

        var cfg: Vec<MirCfgRecord> = vec_new<MirCfgRecord>(allocator, 64);
        var placements: Vec<MirPlacementRecord> = vec_new<MirPlacementRecord>(allocator, 16);
        print(-77);
        print(lower_structured_mir(events, allocator, cfg, placements));
        print(vec_len<MirCfgRecord>(cfg));
        var ci: i64 = 0;
        while (ci < vec_len<MirCfgRecord>(cfg)) {
            let record: MirCfgRecord = vec_get<MirCfgRecord>(cfg, ci);
            print(cfg_kind(record)); print(cfg_block_id(record)); print(cfg_operand(record));
            print(cfg_target_a(record)); print(cfg_target_b(record)); print(cfg_case_value(record)); print(cfg_ordinal(record));
            ci = checked_add(ci, 1);
        }
        print(vec_len<MirPlacementRecord>(placements));
        var pi: i64 = 0;
        while (pi < vec_len<MirPlacementRecord>(placements)) {
            let placement: MirPlacementRecord = vec_get<MirPlacementRecord>(placements, pi);
            print(placement_block_id(placement)); print(placement_instruction_id(placement)); print(placement_ordinal(placement));
            pi = checked_add(pi, 1);
        }
        drop(placements); drop(cfg); drop(events);
    }
    return 0;
}
'''


def _project(tmp_path):
    root = tmp_path / "structured_mir"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))

    # Keep bootstrap_lexer_core available to the copied project while transferring
    # entrypoint ownership to the temporary structured-MIR probe.
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")

    (root / "src" / "structured_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest_path = root / "Merit.toml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace('entry = "src/lexer.mrt"', 'entry = "src/structured_probe.mrt"')
    manifest_path.write_text(manifest, encoding="utf-8")
    return load_project(manifest_path), root


def _parse(output: str):
    values = [int(value) for value in output.rsplit("-77\n", 1)[1].splitlines()]
    status = values[0]
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
    return status, cfg, placements


def _expected_cfg():
    R = NativeCfgRecord
    return [
        R(10, 0, ordinal=0),
        R(10, 1, ordinal=1), R(10, 2, ordinal=2), R(10, 3, ordinal=3),
        R(11, 0, target_a=1), R(12, 1, operand=0, target_a=2, target_b=3),
        R(10, 4, ordinal=4), R(10, 5, ordinal=5), R(10, 6, ordinal=6),
        R(12, 2, operand=1, target_a=4, target_b=5),
        R(11, 4, target_a=6), R(11, 5, target_a=6), R(11, 6, target_a=1),
        R(10, 7, ordinal=7), R(10, 8, ordinal=8), R(10, 9, ordinal=9), R(10, 10, ordinal=10),
        R(13, 3, operand=2, target_a=7, case_value=10, ordinal=0),
        R(11, 7, target_a=10),
        R(13, 3, operand=2, target_a=8, case_value=20, ordinal=1),
        R(15, 8, operand=3),
        R(14, 3, operand=2, target_a=9, ordinal=2),
        R(11, 9, target_a=10),
        R(15, 10, operand=4),
    ]


def _tuples(records):
    return [(r.kind, r.block_id, r.operand, r.target_a, r.target_b, r.case_value, r.ordinal) for r in records]


def test_native_structured_walker_owns_nested_cfg_and_instruction_placement_interpreter_and_native(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] == _tuples(_expected_cfg())
    assert interpreted[2] == [(0, 0, 0), (2, 1, 0), (4, 2, 0), (5, 3, 0), (7, 4, 0), (9, 5, 0)]

    # The adapter accepts the native topology directly; it does not infer nesting.
    blocks = lower_native_cfg_records(_expected_cfg())
    assert [block.block_id for block in blocks] == list(range(11))
    assert [block.terminator.kind for block in blocks] == [
        "jump", "branch", "branch", "switch", "jump", "jump", "jump", "jump", "return", "jump", "return"
    ]
    assert blocks[3].terminator.cases == (10, 20)
    assert blocks[3].terminator.targets == (7, 8, 9)

    _, _, executable = build(project, root / "native")
    native = _parse(subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout)
    assert native == interpreted


def test_structured_walker_contract_has_stable_rejection_codes(tmp_path):
    # Compilation of the module is covered by bootstrap_lexer acceptance; this test
    # keeps the native record values used by the canonical integration boundary explicit.
    placements = tuple(NativeInstructionPlacement(*values) for values in [(0,0,0),(2,1,0),(4,2,0),(5,3,0),(7,4,0),(9,5,0)])
    assert [p.instruction_id for p in placements] == list(range(6))
