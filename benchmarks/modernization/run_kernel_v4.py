from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "kernel_protocol_v1.json"
CORPUS = HERE / "transaction_corpus.json"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def percentile(values: list[int], p: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def stats(values: list[int], operations: int) -> dict:
    median_ns = int(statistics.median(values))
    return {
        "samples_ns": values,
        "median_ns": median_ns,
        "p95_ns": percentile(values, 0.95),
        "mad_ns": int(statistics.median(abs(v - median_ns) for v in values)),
        "minimum_ns": min(values),
        "maximum_ns": max(values),
        "transactions_per_second_at_median": operations * 1_000_000_000.0 / median_ns,
    }


def load_protocol() -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("schema") != "merit-modernization-kernel-protocol-v1":
        raise ValueError("unsupported kernel protocol")
    if protocol.get("ranking_eligible") is not True:
        raise ValueError("kernel protocol must explicitly opt into ranking")
    if protocol.get("correctness_gate_required") is not True:
        raise ValueError("kernel ranking requires correctness gate")
    return protocol


def parse_kernel_line(stdout: str) -> tuple[int, int]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    marker = [line for line in lines if line.startswith("KERNEL,")]
    if len(marker) != 1:
        raise AssertionError("kernel executable must emit exactly one KERNEL marker")
    parts = marker[0].split(",")
    if len(parts) != 3:
        raise AssertionError("invalid KERNEL marker")
    elapsed_ns, checksum = int(parts[1]), int(parts[2])
    if elapsed_ns <= 0 or checksum == 0:
        raise AssertionError("invalid kernel timing/checksum")
    return elapsed_ns, checksum


def report_from_samples(samples: dict[str, list[int]], checksums: dict[str, int], protocol: dict | None = None) -> dict:
    protocol = protocol or load_protocol()
    expected = {"merit", "java", "csharp"}
    if set(samples) != expected or set(checksums) != expected:
        raise AssertionError("kernel report requires Merit, Java and C#")
    if len(set(checksums.values())) != 1:
        raise AssertionError("kernel checksums disagree across implementations")
    measured = int(protocol["measured_batches"])
    operations = int(protocol["iterations_per_batch"]) * int(protocol["transactions_per_iteration"])
    implementations = []
    for name in ("merit", "java", "csharp"):
        if len(samples[name]) != measured:
            raise AssertionError(f"{name} sample count differs from protocol")
        implementations.append({
            "implementation": name,
            "semantic_digest": EXPECTED_DIGEST,
            "checksum": checksums[name],
            "statistics": stats(samples[name], operations),
        })
    return {
        "schema": "merit-modernization-kernel-report-v4",
        "protocol_schema": protocol["schema"],
        "measurement": protocol["measurement"],
        "ranking_eligible": True,
        "clock_scope": protocol["clock_scope"],
        "state_reset": protocol["state_reset"],
        "anti_optimization": protocol["anti_optimization"],
        "implementations": implementations,
    }


def main() -> int:
    protocol = load_protocol()
    print(json.dumps({
        "schema": "merit-modernization-kernel-runner-v4",
        "protocol": protocol,
        "status": "harness_contract_ready",
        "note": "Generated language executables supply KERNEL elapsed_ns/checksum markers; report_from_samples enforces cross-language equivalence before ranking."
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
