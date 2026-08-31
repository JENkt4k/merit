from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = HERE / "transaction_corpus.json"
REFERENCE = HERE / "run_reference.py"
V1 = HERE / "run_comparison.py"
PROTOCOL = HERE / "benchmark_protocol_v1.json"
MERIT_PROJECT = HERE / "merit" / "Merit.toml"
JAVA_SOURCE = HERE / "java" / "ModernizationBenchmark.java"
CSHARP_PROJECT = HERE / "csharp" / "ModernizationBenchmark.csproj"
CSHARP_SOURCE = HERE / "csharp" / "ModernizationBenchmark.cs"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _percentile_nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _stats(values: list[int], transactions: int) -> dict:
    median_ns = int(statistics.median(values))
    deviations = [abs(value - median_ns) for value in values]
    return {
        "samples_ns": values,
        "median_ns": median_ns,
        "p95_ns": _percentile_nearest_rank(values, 0.95),
        "mad_ns": int(statistics.median(deviations)),
        "minimum_ns": min(values),
        "maximum_ns": max(values),
        "process_transactions_per_second_at_median": (transactions * 1_000_000_000.0 / median_ns),
    }


def _run_checked(command: list[str], data: dict, reference, parser) -> int:
    start = perf_counter_ns()
    result = subprocess.run(command, text=True, capture_output=True, check=True)
    elapsed = perf_counter_ns() - start
    semantic = parser.parse_output(result.stdout, data, reference)
    if semantic["outcome_sha256"] != EXPECTED_DIGEST:
        raise AssertionError(f"sample semantic digest mismatch: {command[0]}")
    return elapsed


def _build_commands(work: Path) -> dict[str, list[str]]:
    from merit.project.build import build
    from merit.project.loader import load_project

    project = load_project(MERIT_PROJECT)
    merit_dir = work / "merit"
    _, _, merit_executable = build(project, merit_dir)

    javac = shutil.which("javac")
    java = shutil.which("java")
    dotnet = shutil.which("dotnet")
    if not javac or not java:
        raise RuntimeError("statistical modernization benchmark requires Java 21+")
    if not dotnet:
        raise RuntimeError("statistical modernization benchmark requires .NET 8+")

    java_dir = work / "java"
    java_dir.mkdir()
    subprocess.run([javac, "-d", str(java_dir), str(JAVA_SOURCE)], check=True, text=True, capture_output=True)

    csharp_project_dir = work / "csharp-project"
    csharp_project_dir.mkdir()
    csharp_project = csharp_project_dir / CSHARP_PROJECT.name
    shutil.copy2(CSHARP_PROJECT, csharp_project)
    shutil.copy2(CSHARP_SOURCE, csharp_project_dir / CSHARP_SOURCE.name)
    csharp_dir = work / "csharp"
    subprocess.run(
        [dotnet, "build", str(csharp_project), "-c", "Release", "-o", str(csharp_dir), "--nologo", "-v:q"],
        check=True,
        text=True,
        capture_output=True,
    )
    return {
        "merit": [str(merit_executable)],
        "java": [java, "-cp", str(java_dir), "ModernizationBenchmark"],
        "csharp": [dotnet, str(csharp_dir / "ModernizationBenchmark.dll")],
    }


def run() -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("schema") != "merit-modernization-statistical-protocol-v1":
        raise ValueError("unsupported statistical protocol")
    if protocol.get("ranking_eligible") is not False:
        raise ValueError("process-level protocol must not be marked ranking eligible")

    reference = _module("modernization_reference_statistical", REFERENCE)
    parser = _module("modernization_parser_statistical", V1)
    data = reference.load_corpus(CORPUS)
    expected = reference.execute(data)
    if expected["outcome_sha256"] != EXPECTED_DIGEST:
        raise AssertionError("frozen reference digest changed")

    warmups = int(protocol["warmup_processes"])
    samples = int(protocol["measured_processes"])
    transactions = int(protocol["transactions_per_process"])
    if transactions != len(data["transactions"]):
        raise AssertionError("protocol transaction count differs from frozen corpus")

    with tempfile.TemporaryDirectory(prefix="merit-modernization-statistical-") as tmp:
        commands = _build_commands(Path(tmp))
        results = []
        for implementation, command in commands.items():
            for _ in range(warmups):
                _run_checked(command, data, reference, parser)
            timings = [_run_checked(command, data, reference, parser) for _ in range(samples)]
            results.append({
                "implementation": implementation,
                "semantic_digest": EXPECTED_DIGEST,
                "warmup_processes": warmups,
                "measured_processes": samples,
                "transactions_per_process": transactions,
                "statistics": _stats(timings, transactions),
            })

    return {
        "schema": "merit-modernization-statistical-report-v3",
        "protocol_schema": protocol["schema"],
        "measurement": protocol["measurement"],
        "ranking_eligible": False,
        "correctness_check_each_sample": True,
        "environment": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "implementations": results,
        "limitations": protocol["notes"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible process-level modernization statistics")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(f"schema: {report['schema']}")
        print(f"measurement: {report['measurement']}")
        print("ranking eligible: no")
        for item in report["implementations"]:
            stats = item["statistics"]
            print(
                f"{item['implementation']}: median_ns={stats['median_ns']} "
                f"p95_ns={stats['p95_ns']} mad_ns={stats['mad_ns']}"
            )
        print("note: process/startup statistics are not steady-state kernel-throughput rankings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
