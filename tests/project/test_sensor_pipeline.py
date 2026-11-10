"""Current-language, single-threaded sensor experiment boundaries."""

from pathlib import Path
import subprocess

import pytest

from merit.compiler import Checker, CompileError, parse
from merit.project.cli import main as project_cli_main


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples" / "projects" / "sensor_pipeline"
SOURCE = PROJECT / "src" / "main.mrt"


def test_sensor_ring_reference_native_parity_and_owned_handoff(tmp_path, capsys):
    executable = tmp_path / "sensor_pipeline"
    assert project_cli_main(
        ["verify", str(PROJECT), "--compiler", "reference", "-o", str(executable)]
    ) == 0
    assert "output matches" in capsys.readouterr().out
    completed = subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    assert completed.stdout.splitlines() == [
        "120",  # direct sequential producer -> consumer
        "1", "1", "1", "0",  # fill and reject a fourth sample
        "1", "2", "121",  # pop first sample
        "1",  # wrap and enqueue after freeing one slot
        "1", "3", "1", "4", "1", "5", "0",  # ordered drain, then empty
        "1", "7", "0", "1", "6", "6", "6",  # rejected 7 and received 6 each drop once
    ]


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
