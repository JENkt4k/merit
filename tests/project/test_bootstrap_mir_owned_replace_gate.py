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
    return r'''module bootstrap_owned_replace_probe
import bootstrap_mir_ownership_flow;

capability allocate;

fn run_case(allocator: Allocator, case_kind: i32) -> i32
requires_caps [allocate]
{
    var bindings: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(allocator, 3);
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(0, 0, 1, 1));
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(1, 1, 1, 0));
    vec_push<MirOwnershipBinding>(bindings, ownership_binding(2, 2, 0, 0));
    var input: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(allocator, 8);
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(input, ownership_event_activate(1));
    if (case_kind == 0) {
        vec_push<MirOwnershipEvent>(input, ownership_event_replace_from_binding(0, 1));
    } else {
        if (case_kind == 1) {
            vec_push<MirOwnershipEvent>(input, ownership_event_replace_from_binding(0, 0));
        } else {
            if (case_kind == 2) {
                vec_push<MirOwnershipEvent>(input, ownership_event_replace_from_binding(0, 2));
            } else {
                if (case_kind == 3) {
                    vec_push<MirOwnershipEvent>(input, ownership_event_drop(1));
                    vec_push<MirOwnershipEvent>(input, ownership_event_replace_from_binding(0, 1));
                } else {
                    vec_push<MirOwnershipEvent>(input, ownership_event_drop(0));
                    vec_push<MirOwnershipEvent>(input, ownership_event_replace_from_binding(0, 1));
                }
            }
        }
    }
    vec_push<MirOwnershipEvent>(input, ownership_event_return(-1));
    var output: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(allocator, 12);
    var records: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(allocator, 12);
    let status: i32 = lower_ownership_flow(input, bindings, allocator, output, records);
    if (case_kind == 0) {
        print(status);
        print(validate_ownership_records(records, bindings));
        print(vec_len<MirOwnershipRecord>(records));
        var index: i64 = 0;
        while (index < vec_len<MirOwnershipRecord>(records)) {
            let record: MirOwnershipRecord = vec_get<MirOwnershipRecord>(records, index);
            print(ownership_record_kind(record));
            print(ownership_record_binding_id(record));
            print(ownership_record_other_binding_id(record));
            print(ownership_record_operand_local(record));
            index = checked_add(index, 1);
        }
    }
    drop(records); drop(output); drop(input); drop(bindings);
    return status;
}

fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        print(-111);
        let good: i32 = run_case(allocator, 0);
        print(-112);
        print(run_case(allocator, 1));
        print(run_case(allocator, 2));
        print(run_case(allocator, 3));
        print(run_case(allocator, 4));
    }
    return 0;
}
'''


def _project(tmp_path: Path):
    root = tmp_path / "owned_replace"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "owned_replace_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('entry = "src/lexer.mrt"', 'entry = "src/owned_replace_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _parse(output: str):
    good, bad = output.rsplit("-111\n", 1)[1].split("-112\n", 1)
    values = [int(value) for value in good.splitlines()]
    status, validation, count = values[:3]
    flat = values[3:]
    assert len(flat) == count * 4
    records = [tuple(flat[i:i + 4]) for i in range(0, len(flat), 4)]
    failures = tuple(int(value) for value in bad.splitlines())
    return status, validation, records, failures


def test_owned_binding_replace_preserves_source_identity_interpreter_and_native(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] == 0
    # Replacement emits the old target drop followed by a move whose record
    # names both target binding 0 and consumed source binding 1/local 1.
    assert (4, 0, -1, 0) in interpreted[2]
    assert (5, 0, 1, 1) in interpreted[2]
    # self replacement, non-owned source, consumed source, dead target
    assert interpreted[3] == (68, 71, 73, 72)

    _, _, executable = build(project, root / "native")
    native = _parse(
        subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    )
    assert native == interpreted
