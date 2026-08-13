from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = HERE / "transaction_corpus.json"
REFERENCE = HERE / "run_reference.py"
GENERATOR = HERE / "generate_implementations.py"
PROFILES = HERE / "implementation_profiles_v1.json"
MERIT_PROJECT = HERE / "merit" / "Merit.toml"
MERIT_SOURCE = HERE / "merit" / "src" / "main.mrt"
JAVA_SOURCE = HERE / "java" / "ModernizationBenchmark.java"

CODE_RESULTS = {
    0: "committed",
    1: "invalid_amount",
    2: "same_account",
    3: "wrong_debit_account",
    4: "wrong_credit_account",
    5: "duplicate_or_out_of_order",
    6: "insufficient_funds",
    7: "credit_overflow",
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_metrics(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meaningful = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("//")]
    return {
        "source_bytes": len(text.encode("utf-8")),
        "source_lines": len(text.splitlines()),
        "meaningful_source_lines": len(meaningful),
    }


def parse_output(output: str, data: dict, reference) -> dict:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or lines[0] != "-900":
        raise ValueError("implementation output missing outcome sentinel")
    transaction_count = len(data["transactions"])
    codes = [int(value) for value in lines[1 : 1 + transaction_count]]
    sentinel = 1 + transaction_count
    if len(lines) <= sentinel or lines[sentinel] != "-901":
        raise ValueError("implementation output missing final-state sentinel")
    outcomes = []
    for tx, code in zip(data["transactions"], codes, strict=True):
        result = CODE_RESULTS.get(code)
        if result is None:
            raise ValueError(f"unknown implementation result code {code}")
        outcomes.append({"id": tx["id"], "result": result})

    state = lines[sentinel + 1 :]
    if len(state) != len(data["accounts"]) * 3:
        raise ValueError("implementation output has wrong final-account field count")
    final_accounts = []
    for offset in range(0, len(state), 3):
        amount = Decimal(state[offset + 1])
        scaled = amount * 100
        if scaled != scaled.to_integral_value():
            raise ValueError("implementation emitted fractional minor units")
        final_accounts.append(
            {
                "id": int(state[offset]),
                "balance_minor": int(scaled),
                "last_sequence": int(state[offset + 2]),
            }
        )
    final_accounts.sort(key=lambda item: item["id"])
    committed = sum(item["result"] == "committed" for item in outcomes)
    semantic = {
        "schema": data["schema"],
        "transaction_count": len(outcomes),
        "committed": committed,
        "rejected": len(outcomes) - committed,
        "outcomes": outcomes,
        "final_accounts": final_accounts,
    }
    semantic["outcome_sha256"] = hashlib.sha256(reference.canonical_json(semantic)).hexdigest()
    return semantic


def _version(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=True)
    return (result.stdout or result.stderr).strip().splitlines()[0]


def run_merit(data: dict, reference, work: Path) -> tuple[dict, dict]:
    from merit.project.build import build, interpret
    from merit.project.loader import load_project

    project = load_project(MERIT_PROJECT)
    start = perf_counter_ns()
    interpreted_output = interpret(project)
    interpret_elapsed = perf_counter_ns() - start
    interpreted = parse_output(interpreted_output, data, reference)

    native_dir = work / "merit-native"
    start = perf_counter_ns()
    _, _, executable = build(project, native_dir)
    build_elapsed = perf_counter_ns() - start
    start = perf_counter_ns()
    result = subprocess.run([str(executable)], text=True, capture_output=True, check=True)
    run_elapsed = perf_counter_ns() - start
    native = parse_output(result.stdout, data, reference)
    if native != interpreted:
        raise AssertionError("Merit interpreter/native benchmark outputs diverge")

    metrics = _source_metrics(MERIT_SOURCE)
    metrics.update(
        {
            "implementation": "merit",
            "numeric_model": "language exact decimal USD(18,2,half_even)",
            "correctness": "pass",
            "outcome_sha256": native["outcome_sha256"],
            "interpreter_end_to_end_elapsed_ns": interpret_elapsed,
            "build_elapsed_ns": build_elapsed,
            "run_process_elapsed_ns": run_elapsed,
            "artifact_bytes": executable.stat().st_size,
        }
    )
    return native, metrics


def run_java(data: dict, reference, work: Path) -> tuple[dict, dict]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        raise RuntimeError("Java benchmark requires javac and java")
    out = work / "java-classes"
    out.mkdir(parents=True, exist_ok=True)
    start = perf_counter_ns()
    subprocess.run([javac, "-d", str(out), str(JAVA_SOURCE)], text=True, capture_output=True, check=True)
    build_elapsed = perf_counter_ns() - start
    start = perf_counter_ns()
    result = subprocess.run([java, "-cp", str(out), "ModernizationBenchmark"], text=True, capture_output=True, check=True)
    run_elapsed = perf_counter_ns() - start
    semantic = parse_output(result.stdout, data, reference)
    artifact_bytes = sum(path.stat().st_size for path in out.glob("*.class"))
    metrics = _source_metrics(JAVA_SOURCE)
    metrics.update(
        {
            "implementation": "java",
            "numeric_model": "java.math.BigDecimal with explicit scale-bearing literals",
            "correctness": "pass",
            "outcome_sha256": semantic["outcome_sha256"],
            "build_elapsed_ns": build_elapsed,
            "run_process_elapsed_ns": run_elapsed,
            "artifact_bytes": artifact_bytes,
            "compiler": _version([javac, "-version"]),
            "runtime": _version([java, "-version"]),
        }
    )
    return semantic, metrics


def verify_generated_sources() -> None:
    generator = _load_module("modernization_generator", GENERATOR)
    for path, expected in generator.generated().items():
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise AssertionError(f"generated benchmark source is stale: {path.relative_to(ROOT)}")


def _profiles() -> dict:
    payload = json.loads(PROFILES.read_text(encoding="utf-8"))
    if payload.get("schema") != "merit-modernization-implementation-profiles-v1":
        raise ValueError("unsupported implementation profile schema")
    return payload["implementations"]


def run() -> dict:
    reference = _load_module("modernization_reference", REFERENCE)
    data = reference.load_corpus(CORPUS)
    expected = reference.execute(data)
    profiles = _profiles()
    verify_generated_sources()
    with tempfile.TemporaryDirectory(prefix="merit-modernization-") as tmp:
        work = Path(tmp)
        merit_semantic, merit_metrics = run_merit(data, reference, work)
        java_semantic, java_metrics = run_java(data, reference, work)
    for name, observed in (("merit", merit_semantic), ("java", java_semantic)):
        if observed != expected:
            raise AssertionError(f"{name} semantic output differs from reference")
    merit_metrics["semantic_configuration"] = profiles["merit"]
    java_metrics["semantic_configuration"] = profiles["java"]
    return {
        "schema": "merit-modernization-report-v1",
        "corpus_schema": data["schema"],
        "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "outcome_sha256": expected["outcome_sha256"],
        "correctness_required_for_performance": True,
        "measurement_scope": "single-process invocation/build diagnostics; not a throughput ranking",
        "implementations": [merit_metrics, java_metrics],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Merit and Java modernization baselines")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.json:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(f"schema: {report['schema']}")
        print(f"outcome sha256: {report['outcome_sha256']}")
        for item in report["implementations"]:
            print(
                f"{item['implementation']}: correctness={item['correctness']} "
                f"lines={item['meaningful_source_lines']} artifact_bytes={item['artifact_bytes']} "
                f"build_ns={item['build_elapsed_ns']} run_process_ns={item['run_process_elapsed_ns']}"
            )
            print(f"  numeric policy: {item['semantic_configuration']['numeric_type']}")
        print("performance note: single-process timings are diagnostic only, not a ranking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
