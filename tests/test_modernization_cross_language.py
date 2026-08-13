from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "modernization"
GENERATOR = BENCHMARK / "generate_implementations.py"
COMPARISON = BENCHMARK / "run_comparison.py"
SCHEMA = BENCHMARK / "report_schema_v1.json"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_merit_and_java_sources_are_exactly_derived_from_frozen_corpus():
    generator = _module("modernization_generator_test", GENERATOR)
    for path, expected in generator.generated().items():
        assert path.read_text(encoding="utf-8") == expected


def test_merit_interpreter_native_and_java_match_reference_semantics():
    comparison = _module("modernization_comparison_test", COMPARISON)
    report = comparison.run()

    assert report["schema"] == "merit-modernization-report-v1"
    assert report["outcome_sha256"] == EXPECTED_DIGEST
    assert report["correctness_required_for_performance"] is True
    assert {item["implementation"] for item in report["implementations"]} == {"merit", "java"}
    assert {item["correctness"] for item in report["implementations"]} == {"pass"}
    assert {item["outcome_sha256"] for item in report["implementations"]} == {EXPECTED_DIGEST}
    for item in report["implementations"]:
        assert item["source_bytes"] > 0
        assert item["meaningful_source_lines"] > 0
        assert item["build_elapsed_ns"] >= 0
        assert item["run_process_elapsed_ns"] >= 0
        assert item["artifact_bytes"] > 0


def test_report_schema_requires_correctness_before_performance():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["schema"]["const"] == "merit-modernization-report-v1"
    assert schema["properties"]["correctness_required_for_performance"]["const"] is True
    implementation = schema["properties"]["implementations"]["items"]
    assert implementation["properties"]["correctness"]["const"] == "pass"
    assert "outcome_sha256" in implementation["required"]
    assert "build_elapsed_ns" in implementation["required"]
    assert "run_process_elapsed_ns" in implementation["required"]
