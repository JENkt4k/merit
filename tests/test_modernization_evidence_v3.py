from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "modernization"
STATISTICAL = BENCHMARK / "run_statistical_v3.py"
DEFECTS = BENCHMARK / "run_defect_matrix.py"
PROTOCOL = BENCHMARK / "benchmark_protocol_v1.json"
DEFECT_SPEC = BENCHMARK / "defect_probes_v1.json"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_statistical_protocol_is_explicitly_not_kernel_ranking():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["schema"] == "merit-modernization-statistical-protocol-v1"
    assert protocol["ranking_eligible"] is False
    assert protocol["correctness_check_each_sample"] is True
    assert protocol["warmup_processes"] >= 1
    assert protocol["measured_processes"] >= 5
    assert {"median", "p95", "mad"}.issubset(protocol["statistics"])


def test_statistical_runner_reproduces_semantics_for_every_language_and_sample():
    statistical = _module("modernization_statistical_test", STATISTICAL)
    report = statistical.run()
    assert report["schema"] == "merit-modernization-statistical-report-v3"
    assert report["ranking_eligible"] is False
    assert report["correctness_check_each_sample"] is True
    assert {item["implementation"] for item in report["implementations"]} == {"merit", "java", "csharp"}
    for item in report["implementations"]:
        assert item["semantic_digest"] == EXPECTED_DIGEST
        assert len(item["statistics"]["samples_ns"]) == item["measured_processes"]
        assert item["statistics"]["median_ns"] > 0
        assert item["statistics"]["p95_ns"] >= item["statistics"]["median_ns"]
        assert item["statistics"]["mad_ns"] >= 0
        assert item["statistics"]["process_transactions_per_second_at_median"] > 0


def test_defect_matrix_is_executable_and_matches_declared_scope():
    specification = json.loads(DEFECT_SPEC.read_text(encoding="utf-8"))
    assert specification["schema"] == "merit-modernization-defect-probes-v1"
    defects = _module("modernization_defects_test", DEFECTS)
    report = defects.run()
    assert report["schema"] == "merit-modernization-defect-matrix-v1"
    assert len(report["probes"]) == 3
    for probe in report["probes"]:
        assert probe["observed"]["merit"] == "compiler"
        assert probe["observed"]["java"] == "not_caught_at_compile_time"
        assert probe["observed"]["csharp"] == "not_caught_at_compile_time"
