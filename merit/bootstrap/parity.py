"""Deterministic bootstrap stage parity accounting.

This module records what each compiler stage produced without deciding language
semantics. It is intentionally small enough to remain useful for AST, HIR, MIR,
and runtime comparison as those stages come online.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping

from .corpus import BootstrapCorpus, CorpusContractError, KNOWN_STAGES


class ParityContractError(ValueError):
    """Raised for incomplete or contradictory parity results."""


@dataclass(frozen=True, slots=True)
class StageObservation:
    case_id: str
    stage: str
    implementation: str
    canonical: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CaseParity:
    case_id: str
    stage: str
    reference_digest: str
    bootstrap_digest: str

    @property
    def matches(self) -> bool:
        return self.reference_digest == self.bootstrap_digest


@dataclass(frozen=True, slots=True)
class ParityReport:
    schema: str
    results: tuple[CaseParity, ...]

    @property
    def matched(self) -> int:
        return sum(result.matches for result in self.results)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def complete(self) -> bool:
        return self.matched == self.total

    def stage_counts(self) -> dict[str, tuple[int, int]]:
        counts: dict[str, list[int]] = {}
        for result in self.results:
            matched, total = counts.setdefault(result.stage, [0, 0])
            counts[result.stage] = [matched + int(result.matches), total + 1]
        return {stage: (values[0], values[1]) for stage, values in sorted(counts.items())}

    def mismatches(self) -> tuple[CaseParity, ...]:
        return tuple(result for result in self.results if not result.matches)

    def to_data(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "matched": self.matched,
            "total": self.total,
            "complete": self.complete,
            "stages": {
                stage: {"matched": matched, "total": total}
                for stage, (matched, total) in self.stage_counts().items()
            },
            "results": [
                {
                    "case": result.case_id,
                    "stage": result.stage,
                    "reference": result.reference_digest,
                    "bootstrap": result.bootstrap_digest,
                    "matches": result.matches,
                }
                for result in self.results
            ],
        }


def canonical_digest(value: object) -> str:
    if isinstance(value, str):
        canonical = value
    else:
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def observe(case_id: str, stage: str, implementation: str, value: object) -> StageObservation:
    if stage not in KNOWN_STAGES:
        raise ParityContractError(f"unknown stage: {stage}")
    if implementation not in {"reference", "bootstrap"}:
        raise ParityContractError(f"unknown implementation: {implementation}")
    if not case_id:
        raise ParityContractError("case id must not be empty")
    canonical = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))
    return StageObservation(case_id, stage, implementation, canonical)


def build_parity_report(
    corpus: BootstrapCorpus,
    observations: Iterable[StageObservation],
    *,
    stages: Iterable[str] | None = None,
) -> ParityReport:
    selected = tuple(sorted(set(stages if stages is not None else KNOWN_STAGES)))
    for stage in selected:
        if stage not in KNOWN_STAGES:
            raise ParityContractError(f"unknown stage: {stage}")

    indexed: dict[tuple[str, str, str], StageObservation] = {}
    for observation in observations:
        key = (observation.case_id, observation.stage, observation.implementation)
        if key in indexed:
            raise ParityContractError(f"duplicate observation: {key}")
        indexed[key] = observation

    results: list[CaseParity] = []
    for case in corpus.cases:
        for stage in case.compare:
            if stage not in selected:
                continue
            reference_key = (case.case_id, stage, "reference")
            bootstrap_key = (case.case_id, stage, "bootstrap")
            missing = [key for key in (reference_key, bootstrap_key) if key not in indexed]
            if missing:
                raise ParityContractError(f"missing observations: {missing}")
            reference = indexed.pop(reference_key)
            bootstrap = indexed.pop(bootstrap_key)
            results.append(CaseParity(case.case_id, stage, reference.digest, bootstrap.digest))

    relevant_extras = [key for key in indexed if key[1] in selected]
    if relevant_extras:
        raise ParityContractError(f"observations do not belong to selected corpus gates: {sorted(relevant_extras)}")

    return ParityReport("bootstrap-parity-v1", tuple(results))


def canonical_report_json(report: ParityReport) -> str:
    return json.dumps(report.to_data(), sort_keys=True, separators=(",", ":"))


def markdown_summary(report: ParityReport) -> str:
    status = "PASS" if report.complete else "FAIL"
    lines = [
        "## Bootstrap parity",
        "",
        f"**{status}: {report.matched}/{report.total} stage comparisons match.**",
        "",
        "| Stage | Matched | Total |",
        "|---|---:|---:|",
    ]
    for stage, (matched, total) in report.stage_counts().items():
        lines.append(f"| `{stage}` | {matched} | {total} |")
    mismatches = report.mismatches()
    if mismatches:
        lines.extend(["", "### Mismatches", ""])
        for result in mismatches:
            lines.append(f"- `{result.case_id}` / `{result.stage}`")
    return "\n".join(lines) + "\n"
