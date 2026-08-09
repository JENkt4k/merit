"""Adapter for the repository's established bootstrap-corpus-v1 JSON shape."""

from __future__ import annotations

import json
from pathlib import Path

from .corpus import (
    CORPUS_SCHEMA,
    KNOWN_STAGES,
    BootstrapCorpus,
    CorpusCase,
    CorpusContractError,
)


def _repository_compare(raw: object, case_id: str, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if raw is None:
        return default
    if not isinstance(raw, list) or not raw or not all(isinstance(stage, str) for stage in raw):
        raise CorpusContractError(f"case {case_id!r} has invalid compare list")
    compare = tuple(raw)
    if len(set(compare)) != len(compare):
        raise CorpusContractError(f"case {case_id!r} repeats compare stage")
    unknown = [stage for stage in compare if stage not in KNOWN_STAGES]
    if unknown:
        raise CorpusContractError(f"case {case_id!r} has unknown compare stage {unknown[0]!r}")
    return compare


def load_repository_corpus(path: str | Path) -> BootstrapCorpus:
    manifest_path = Path(path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CorpusContractError(f"invalid corpus JSON: {error}") from error
    if not isinstance(data, dict):
        raise CorpusContractError("corpus root must be an object")
    if data.get("contract") != CORPUS_SCHEMA:
        raise CorpusContractError(
            f"expected contract {CORPUS_SCHEMA!r}, got {data.get('contract')!r}"
        )
    source_cases = data.get("source_cases")
    expression_cases = data.get("expression_cases")
    if not isinstance(source_cases, list) or not source_cases:
        raise CorpusContractError("source_cases must be a non-empty list")
    if not isinstance(expression_cases, list) or not expression_cases:
        raise CorpusContractError("expression_cases must be a non-empty list")

    cases: list[CorpusCase] = []
    seen: set[str] = set()
    for index, raw in enumerate(source_cases):
        if not isinstance(raw, dict):
            raise CorpusContractError(f"source case {index} must be an object")
        case_id = raw.get("id")
        source = raw.get("source")
        if not isinstance(case_id, str) or not case_id:
            raise CorpusContractError(f"source case {index} has invalid id")
        if case_id in seen:
            raise CorpusContractError(f"duplicate corpus case id: {case_id}")
        if not isinstance(source, str) or not source:
            raise CorpusContractError(f"source case {case_id!r} has invalid source")
        compare = _repository_compare(raw.get("compare"), case_id, default=("tokens",))
        if "tokens" not in compare:
            raise CorpusContractError(f"source case {case_id!r} must compare tokens")
        seen.add(case_id)
        cases.append(CorpusCase(case_id, "source", source, compare))

    for index, raw in enumerate(expression_cases):
        if not isinstance(raw, dict):
            raise CorpusContractError(f"expression case {index} must be an object")
        case_id = raw.get("id")
        expression = raw.get("expression")
        if not isinstance(case_id, str) or not case_id:
            raise CorpusContractError(f"expression case {index} has invalid id")
        if case_id in seen:
            raise CorpusContractError(f"duplicate corpus case id: {case_id}")
        if not isinstance(expression, str) or not expression:
            raise CorpusContractError(f"expression case {case_id!r} has invalid expression")
        compare = _repository_compare(
            raw.get("compare"), case_id, default=("expressions", "ast")
        )
        if "expressions" not in compare:
            raise CorpusContractError(f"expression case {case_id!r} must compare expressions")
        if "ast" not in compare:
            raise CorpusContractError(f"expression case {case_id!r} must compare ast")
        if "hir" in compare and "ast" not in compare:
            raise CorpusContractError(f"HIR case {case_id!r} must also compare ast")
        seen.add(case_id)
        cases.append(CorpusCase(case_id, "expression", expression, compare))

    return BootstrapCorpus(CORPUS_SCHEMA, tuple(cases))
