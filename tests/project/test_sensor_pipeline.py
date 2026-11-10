"""Current-language, single-threaded sensor experiment boundaries."""

from pathlib import Path
import shutil
import subprocess

import pytest

from merit.compiler import Checker, CompileError, parse
from merit.project.cli import main as project_cli_main
from merit.project.build import build
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples" / "projects" / "sensor_pipeline"
SOURCE = PROJECT / "src" / "main.mrt"
EXPECTED_LINES = [
    "120",  # direct sequential producer -> consumer
    "1", "1", "1", "0",  # fill and reject a fourth sample
    "1", "2", "121",  # pop first sample
    "1",  # wrap and enqueue after freeing one slot
    "1", "3", "1", "4", "1", "5", "0",  # ordered drain, then empty
    "1", "7", "0", "1", "6", "6", "6",  # rejected 7 and received 6 each drop once
]


def test_sensor_ring_reference_native_parity_and_owned_handoff(tmp_path, capsys):
    executable = tmp_path / "sensor_pipeline"
    assert project_cli_main(
        ["verify", str(PROJECT), "--compiler", "reference", "-o", str(executable)]
    ) == 0
    assert "output matches" in capsys.readouterr().out
    completed = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    assert completed.stdout.splitlines() == EXPECTED_LINES


def test_sequential_sensor_builds_through_replacement_compiler(tmp_path, capsys):
    compiler_root = tmp_path / "compiler"
    shutil.copytree(
        ROOT / "examples" / "projects" / "bootstrap_lexer", compiler_root,
        ignore=shutil.ignore_patterns("build", ".merit"),
    )
    compiler_manifest = compiler_root / "Merit.toml"
    compiler_manifest.write_text(
        compiler_manifest.read_text(encoding="utf-8")
        + '\n[executable]\nadapter = "stdin-string-i32"\n'
        + 'entry = "emit_native_project_artifacts"\n',
        encoding="utf-8", newline="\n",
    )
    _, _, compiler = build(load_project(compiler_manifest), tmp_path / "compiler-stage0")
    sensor_root = tmp_path / "sensor"
    shutil.copytree(PROJECT, sensor_root)
    (sensor_root / "src" / "main.mrt").write_text(
        """module sensor_pipeline
struct Sample { sequence: u64; distance_mm: i32; }
fn consume(borrow sample: Sample) -> i32 { return sample.distance_mm; }
fn main() -> i32 {
    let sample: Sample = Sample { sequence: 1, distance_mm: 120 };
    print(consume(sample));
    return 0;
}
""",
        encoding="utf-8", newline="\n",
    )
    output = tmp_path / "sensor-replacement"
    assert project_cli_main([
        "build", str(sensor_root), "--compiler-path", str(compiler), "-o", str(output),
    ]) == 0
    assert str(output) in capsys.readouterr().out
    completed = subprocess.run([str(output)], capture_output=True, text=True, check=True)
    assert completed.stdout.splitlines() == ["120"]


def test_owned_packet_cannot_be_used_after_vector_handoff():
    source = SOURCE.read_text(encoding="utf-8")
    old = "print(owned_slot_send(owned_slot, packet));"
    assert old in source
    bad = source.replace(old, old + "\n        print(packet.sample.sequence);", 1)
    with pytest.raises(CompileError, match="moved value packet"):
        Checker(parse(bad)).check()


def test_allocation_without_capability_is_rejected():
    bad = """module sensor_bad
capability allocate;
fn main() -> i32 {
    let a: Allocator = system_allocator();
    let values: Vec<i32> = vec_new<i32>(a, 1);
    drop(values);
    return 0;
}
"""
    with pytest.raises(CompileError, match="requires capabilities"):
        Checker(parse(bad)).check()


def test_single_thread_owned_fifo_uses_two_vectors_without_indexed_take(tmp_path, capsys):
    """A bounded-capacity FIFO can move owned packets via two stack vectors."""
    project = tmp_path / "owned_fifo"
    source_dir = project / "src"
    source_dir.mkdir(parents=True)
    (project / "Merit.toml").write_text(
        '[package]\nname = "owned_fifo"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    (source_dir / "main.mrt").write_text(
        """module owned_fifo
capability allocate;
struct Packet { sequence: i32; payload: Buffer; }
destructor Packet { print(self.sequence); }
enum SendOutcome { Accepted, Rejected(Packet) }
fn try_send(borrow_mut incoming: Vec<Packet>, borrow_mut outgoing: Vec<Packet>,
            packet: Packet, capacity: i64) -> SendOutcome
requires_caps [allocate]
{
    if (vec_len<Packet>(incoming) + vec_len<Packet>(outgoing) == capacity) {
        return Rejected(packet);
    } else {
        vec_push<Packet>(incoming, packet);
        return Accepted();
    }
}
fn take(borrow_mut incoming: Vec<Packet>, borrow_mut outgoing: Vec<Packet>) -> Packet
requires_caps [allocate]
{
    if (vec_len<Packet>(outgoing) == 0) {
        while (vec_len<Packet>(incoming) > 0) {
            let item: Packet = vec_pop<Packet>(incoming);
            vec_push<Packet>(outgoing, item);
        }
    }
    return vec_pop<Packet>(outgoing);
}
fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var incoming: Vec<Packet> = vec_new<Packet>(allocator, 3);
        var outgoing: Vec<Packet> = vec_new<Packet>(allocator, 3);
        let p1: Packet = Packet { sequence: 1, payload: buffer_from_string(allocator, "a") };
        let p2: Packet = Packet { sequence: 2, payload: buffer_from_string(allocator, "bb") };
        let p3: Packet = Packet { sequence: 3, payload: buffer_from_string(allocator, "ccc") };
        vec_push<Packet>(incoming, p1);
        vec_push<Packet>(incoming, p2);
        vec_push<Packet>(incoming, p3);
        let full_packet: Packet = Packet { sequence: 4, payload: buffer_from_string(allocator, "dddd") };
        let full: SendOutcome = try_send(incoming, outgoing, full_packet, 3);
        match (full) {
            Accepted => { print(99); }
            Rejected(returned) => {
                print(returned.sequence);
                drop(returned);
            }
        }
        let first: Packet = take(incoming, outgoing);
        print(buffer_len(first.payload));
        drop(first);
        let p5: Packet = Packet { sequence: 5, payload: buffer_from_string(allocator, "eeeee") };
        let accepted: SendOutcome = try_send(incoming, outgoing, p5, 3);
        match (accepted) {
            Accepted => { print(1); }
            Rejected(returned) => { drop(returned); print(99); }
        }
        let second: Packet = take(incoming, outgoing);
        print(buffer_len(second.payload));
        drop(second);
        let third: Packet = take(incoming, outgoing);
        print(buffer_len(third.payload));
        drop(third);
        let fourth: Packet = take(incoming, outgoing);
        print(buffer_len(fourth.payload));
        drop(fourth);
        drop(outgoing);
        drop(incoming);
    }
    return 0;
}
""",
        encoding="utf-8", newline="\n",
    )
    executable = tmp_path / "owned_fifo_program"
    assert project_cli_main(
        ["verify", str(project), "--compiler", "reference", "-o", str(executable)]
    ) == 0
    assert "output matches" in capsys.readouterr().out
    completed = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    assert completed.stdout.splitlines() == [
        "4", "4", "1", "1", "1", "2", "2", "3", "3", "5", "5",
    ]
