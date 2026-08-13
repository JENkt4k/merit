from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "modernization"
GENERATOR = BENCHMARK / "generate_csharp.py"
COMPARISON = BENCHMARK / "run_comparison_v2.py"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_csharp_source_is_exactly_derived_from_frozen_corpus():
    generator = _module("modernization_csharp_generator_test", GENERATOR)
    assert generator.CSHARP_OUT.read_text(encoding="utf-8") == generator.generate(generator.load_corpus())


def test_merit_java_and_csharp_match_reference_semantics():
    comparison = _module("modernization_comparison_v2_test", COMPARISON)
    report = comparison.run()
    assert report["schema"] == "merit-modernization-report-v2"
    assert report["outcome_sha256"] == EXPECTED_DIGEST
    assert report["correctness_required_for_performance"] is True
    assert {item["implementation"] for item in report["implementations"]} == {"merit", "java", "csharp"}
    assert {item["correctness"] for item in report["implementations"]} == {"pass"}
    assert {item["outcome_sha256"] for item in report["implementations"]} == {EXPECTED_DIGEST}
    assert report["environment"]["os"]
    for item in report["implementations"]:
        assert item["source_bytes"] > 0
        assert item["meaningful_source_lines"] > 0
        assert item["artifact_bytes"] > 0
