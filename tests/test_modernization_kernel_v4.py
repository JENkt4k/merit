from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "modernization"
PROTOCOL = BENCHMARK / "kernel_protocol_v1.json"
RUNNER = BENCHMARK / "run_kernel_v4.py"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kernel_protocol_defines_narrow_ranking_boundary():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["schema"] == "merit-modernization-kernel-protocol-v1"
    assert protocol["ranking_eligible"] is True
    assert protocol["correctness_gate_required"] is True
    assert protocol["warmup_batches"] >= 3
    assert protocol["measured_batches"] >= 9
    assert protocol["iterations_per_batch"] >= 1000
    assert "startup" in protocol["clock_scope"]
    assert "checksum" in protocol["anti_optimization"]


def test_kernel_marker_parser_rejects_ambiguous_or_dead_results():
    runner = _module("kernel_runner_parser", RUNNER)
    assert runner.parse_kernel_line("noise\nKERNEL,12345,99\n") == (12345, 99)
    for invalid in ("", "KERNEL,0,99", "KERNEL,1,0", "KERNEL,1,2\nKERNEL,3,4"):
        try:
            runner.parse_kernel_line(invalid)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"accepted invalid kernel output: {invalid!r}")


def test_kernel_report_requires_cross_language_checksum_equivalence():
    runner = _module("kernel_runner_report", RUNNER)
    protocol = runner.load_protocol()
    n = protocol["measured_batches"]
    samples = {
        "merit": [1000 + i for i in range(n)],
        "java": [900 + i for i in range(n)],
        "csharp": [950 + i for i in range(n)],
    }
    report = runner.report_from_samples(samples, {"merit": 77, "java": 77, "csharp": 77}, protocol)
    assert report["schema"] == "merit-modernization-kernel-report-v4"
    assert report["ranking_eligible"] is True
    assert {item["implementation"] for item in report["implementations"]} == {"merit", "java", "csharp"}
    assert all(item["semantic_digest"] == EXPECTED_DIGEST for item in report["implementations"])
    assert all(item["statistics"]["transactions_per_second_at_median"] > 0 for item in report["implementations"])

    try:
        runner.report_from_samples(samples, {"merit": 77, "java": 78, "csharp": 77}, protocol)
    except AssertionError as error:
        assert "checksums disagree" in str(error)
    else:
        raise AssertionError("accepted unequal cross-language checksums")
