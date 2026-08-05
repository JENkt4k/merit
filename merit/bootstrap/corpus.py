"""Versioned bootstrap corpus loading and validation.

The corpus is an executable contract shared by the Python reference compiler,
the Merit-native bootstrap compiler, and later AST/HIR/MIR parity stages.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence


CORPUS_SCHEMA = "bootstrap-corpus-v1"
KNOWN_STAGES = frozenset({"tokens", "syntax", "diagnostics", "expressions", "ast", "hir", "mir", "interpreter", "native"})
KNOWN_KINDS = frozenset({"source", "expression"})


class CorpusContractError(ValueError):
    """Raised when a bootstrap corpus manifest violates its versioned schema."""


@dataclass(frozen=True, slots=True)
class CorpusCase:
    case_id: str
    kind: str
    text: str
    compare: tuple[str, ...]

    def requires(self, stage: str) -> bool:
        return stage in self.compare


@dataclass(frozen=True, slots=True)
class BootstrapCorpus:
    schema: str
    cases: tuple[CorpusCase, ...]

    def by_id(self, case_id: str) -> CorpusCase:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise KeyError(case_id)

    def for_stage(self, stage: str) -> tuple[CorpusCase, ...]:
        _validate_stage(stage)
        return tuple(case for case in self.cases if case.requires(stage))

    def by_kind(self, kind: str) -> tuple[CorpusCase, ...]:
        if kind not in KNOWN_KINDS:
            raise CorpusContractError(f"unknown corpus case kind: {kind}")
        return tuple(case for case in self.cases if case.kind == kind)

    def stage_counts(self) -> dict[str, int]:
        return {stage: len(self.for_stage(stage)) for stage in sorted(KNOWN_STAGES)}

    def to_data(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cases": [
                {
                    "id": case.case_id,
                    "kind": case.kind,
                    "text": case.text,
                    "compare": list(case.compare),
                }
                for case in self.cases
            ],
        }


def _validate_stage(stage: str) -> None:
    if stage not in KNOWN_STAGES:
        raise CorpusContractError(f"unknown bootstrap stage: {stage}")


def _require_string(value: object, field: str, index: int) -> str:
    if not isinstance(value, str) or not value:
        raise CorpusContractError(f"case {index} field {field!r} must be a non-empty string")
    return value


def _parse_compare(value: object, index: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CorpusContractError(f"case {index} compare must be a non-empty list")
    stages: list[str] = []
    seen: set[str] = set()
    for raw in value:
        stage = _require_string(raw, "compare item", index)
        _validate_stage(stage)
        if stage in seen:
            raise CorpusContractError(f"case {index} repeats compare stage {stage!r}")
        seen.add(stage)
        stages.append(stage)
    return tuple(stages)


def parse_corpus(data: Mapping[str, object]) -> BootstrapCorpus:
    schema = data.get("schema")
    if schema != CORPUS_SCHEMA:
        raise CorpusContractError(f"expected schema {CORPUS_SCHEMA!r}, got {schema!r}")
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CorpusContractError("corpus cases must be a non-empty list")

    cases: list[CorpusCase] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise CorpusContractError(f"case {index} must be an object")
        case_id = _require_string(raw.get("id"), "id", index)
        if case_id in identifiers:
            raise CorpusContractError(f"duplicate corpus case id: {case_id}")
        identifiers.add(case_id)
        kind = _require_string(raw.get("kind"), "kind", index)
        if kind not in KNOWN_KINDS:
            raise CorpusContractError(f"case {case_id!r} has unknown kind {kind!r}")
        text = _require_string(raw.get("text"), "text", index)
        compare = _parse_compare(raw.get("compare"), index)

        if kind == "expression" and "expressions" not in compare:
            raise CorpusContractError(f"expression case {case_id!r} must compare expressions")
        if "ast" in compare and "expressions" not in compare:
            raise CorpusContractError(f"AST case {case_id!r} must also compare expressions")
        if kind == "source" and "tokens" not in compare:
            raise CorpusContractError(f"source case {case_id!r} must compare tokens")

        cases.append(CorpusCase(case_id, kind, text, compare))

    return BootstrapCorpus(CORPUS_SCHEMA, tuple(cases))


def load_corpus(path: str | Path) -> BootstrapCorpus:
    manifest_path = Path(path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CorpusContractError(f"invalid corpus JSON: {error}") from error
    if not isinstance(raw, dict):
        raise CorpusContractError("corpus root must be an object")
    return parse_corpus(raw)


def canonical_corpus_json(corpus: BootstrapCorpus) -> str:
    return json.dumps(corpus.to_data(), sort_keys=True, separators=(",", ":"))
