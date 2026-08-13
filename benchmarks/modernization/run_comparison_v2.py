from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = HERE / "transaction_corpus.json"
REFERENCE = HERE / "run_reference.py"
V1 = HERE / "run_comparison.py"
CSHARP_GENERATOR = HERE / "generate_csharp.py"
CSHARP_SOURCE = HERE / "csharp" / "ModernizationBenchmark.cs"
CSHARP_PROJECT = HERE / "csharp" / "ModernizationBenchmark.csproj"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _version(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=True)
    return (result.stdout or result.stderr).strip().splitlines()[0]


def _source_metrics(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meaningful = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("//")]
    return {"source_bytes": len(text.encode()), "source_lines": len(text.splitlines()), "meaningful_source_lines": len(meaningful)}


def run_csharp(data: dict, reference, work: Path) -> tuple[dict, dict]:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError("C# modernization benchmark requires dotnet SDK 8+")
    generator = _module("modernization_csharp_generator", CSHARP_GENERATOR)
    if CSHARP_SOURCE.read_text(encoding="utf-8") != generator.generate(data):
        raise AssertionError("generated C# benchmark source is stale")

    out = work / "csharp"
    start = perf_counter_ns()
    subprocess.run(
        [dotnet, "build", str(CSHARP_PROJECT), "-c", "Release", "-o", str(out), "--nologo", "-v:q"],
        text=True, capture_output=True, check=True,
    )
    build_elapsed = perf_counter_ns() - start
    dll = out / "ModernizationBenchmark.dll"
    start = perf_counter_ns()
    result = subprocess.run([dotnet, str(dll)], text=True, capture_output=True, check=True)
    run_elapsed = perf_counter_ns() - start
    v1 = _module("modernization_v1_parser", V1)
    semantic = v1.parse_output(result.stdout, data, reference)
    metrics = _source_metrics(CSHARP_SOURCE)
    metrics.update({
        "implementation": "csharp",
        "numeric_model": "System.Decimal with checked application arithmetic",
        "correctness": "pass",
        "outcome_sha256": semantic["outcome_sha256"],
        "build_elapsed_ns": build_elapsed,
        "run_process_elapsed_ns": run_elapsed,
        "artifact_bytes": sum(p.stat().st_size for p in out.iterdir() if p.is_file()),
        "runtime": _version([dotnet, "--version"]),
        "semantic_configuration": {
            "numeric_type": "System.Decimal value type",
            "precision_policy": "96-bit integer coefficient with 0-28 decimal scale; workload literals are exact",
            "scale_policy": "application literals carry scale; domain requires cents at the corpus boundary",
            "rounding_policy": "no rounding occurs in this add/subtract workload",
            "range_policy": "long identifiers/sequences plus explicit maximum-balance business rule",
            "overflow_policy": "checked decimal arithmetic plus explicit business maximum",
            "representation_boundary": "canonical financial values; legacy physical encoding requires a separate adapter"
        },
    })
    return semantic, metrics


def run() -> dict:
    reference = _module("modernization_reference_v2", REFERENCE)
    data = reference.load_corpus(CORPUS)
    expected = reference.execute(data)
    v1 = _module("modernization_comparison_v1", V1)
    base = v1.run()
    with tempfile.TemporaryDirectory(prefix="merit-modernization-v2-") as tmp:
        csharp_semantic, csharp_metrics = run_csharp(data, reference, Path(tmp))
    if csharp_semantic != expected:
        raise AssertionError("csharp semantic output differs from reference")
    return {
        "schema": "merit-modernization-report-v2",
        "corpus_schema": data["schema"],
        "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "outcome_sha256": expected["outcome_sha256"],
        "correctness_required_for_performance": True,
        "measurement_scope": "cross-language semantic and build/process diagnostics; throughput ranking remains disabled",
        "environment": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "implementations": [*base["implementations"], csharp_metrics],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Merit, Java, and C# modernization baselines")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(f"schema: {report['schema']}")
        print(f"outcome sha256: {report['outcome_sha256']}")
        for item in report["implementations"]:
            print(f"{item['implementation']}: correctness={item['correctness']} lines={item['meaningful_source_lines']} artifact_bytes={item['artifact_bytes']}")
        print("performance note: throughput ranking remains disabled until in-process protocol lands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
