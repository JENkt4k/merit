import json
from pathlib import Path

import pytest

from merit.bootstrap.ast_contract import canonical_ast_json, lower_expression_ast
from merit.bootstrap.corpus import (
    CORPUS_SCHEMA,
    CorpusContractError,
    canonical_corpus_json,
    load_corpus,
    parse_corpus,
)
from merit.bootstrap.parity import (
    ParityContractError,
    build_parity_report,
    canonical_digest,
    canonical_report_json,
    markdown_summary,
    observe,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/project/bootstrap_corpus_v1.json"


def minimal_data(**case_overrides):
    case = {
        "id": "simple-expression",
        "kind": "expression",
        "text": "1+2",
        "compare": ["expressions", "ast"],
    }
    case.update(case_overrides)
    return {"schema": CORPUS_SCHEMA, "cases": [case]}


def test_repository_bootstrap_corpus_is_valid_and_queryable():
    corpus = load_corpus(MANIFEST)
    assert corpus.schema == CORPUS_SCHEMA
    assert len(corpus.cases) == 23
    assert len(corpus.by_kind("source")) == 11
    assert len(corpus.by_kind("expression")) == 12
    assert len(corpus.for_stage("ast")) == 12
    assert corpus.by_id("expr-precedence").text == "1+2*3"
    assert corpus.stage_counts()["tokens"] == 11


def test_corpus_canonical_json_round_trips():
    corpus = load_corpus(MANIFEST)
    encoded = canonical_corpus_json(corpus)
    assert parse_corpus(json.loads(encoded)) == corpus
    assert " " not in encoded
    assert "\n" not in encoded


@pytest.mark.parametrize(
    "data, message",
    [
        ({"schema": "wrong", "cases": []}, "expected schema"),
        ({"schema": CORPUS_SCHEMA, "cases": []}, "non-empty list"),
        ({"schema": CORPUS_SCHEMA, "cases": [1]}, "must be an object"),
        (minimal_data(id=""), "field 'id'"),
        (minimal_data(kind="unknown"), "unknown kind"),
        (minimal_data(text=""), "field 'text'"),
        (minimal_data(compare=[]), "non-empty list"),
        (minimal_data(compare=["unknown"]), "unknown bootstrap stage"),
        (minimal_data(compare=["ast", "ast", "expressions"]), "repeats compare stage"),
        (minimal_data(compare=["ast"]), "must also compare expressions"),
        (minimal_data(kind="expression", compare=["tokens"]), "must compare expressions"),
        (minimal_data(kind="source", compare=["syntax"]), "must compare tokens"),
    ],
)
def test_invalid_corpus_contracts_are_rejected(data, message):
    with pytest.raises(CorpusContractError, match=message):
        parse_corpus(data)


def test_duplicate_corpus_identifiers_are_rejected():
    data = minimal_data()
    data["cases"].append(dict(data["cases"][0]))
    with pytest.raises(CorpusContractError, match="duplicate corpus case id"):
        parse_corpus(data)


def test_unknown_corpus_queries_are_rejected():
    corpus = parse_corpus(minimal_data())
    with pytest.raises(CorpusContractError, match="unknown corpus case kind"):
        corpus.by_kind("statement")
    with pytest.raises(CorpusContractError, match="unknown bootstrap stage"):
        corpus.for_stage("lowering")
    with pytest.raises(KeyError):
        corpus.by_id("absent")


def test_invalid_json_is_reported_as_corpus_error(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(CorpusContractError, match="invalid corpus JSON"):
        load_corpus(path)


def test_non_object_json_root_is_rejected(tmp_path):
    path = tmp_path / "array.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(CorpusContractError, match="root must be an object"):
        load_corpus(path)


def test_canonical_digest_is_stable_for_structured_values():
    assert canonical_digest({"b": 2, "a": [1]}) == canonical_digest({"a": [1], "b": 2})
    assert canonical_digest("literal") != canonical_digest({"literal": True})
    assert len(canonical_digest({"value": 1})) == 64


def observations_for(corpus, *, mismatch=None, stages=("ast",)):
    observations = []
    for case in corpus.cases:
        for stage in case.compare:
            if stage not in stages:
                continue
            value = {"case": case.case_id, "stage": stage, "value": case.text}
            bootstrap = value
            if mismatch == (case.case_id, stage):
                bootstrap = {**value, "value": "different"}
            observations.extend(
                [
                    observe(case.case_id, stage, "reference", value),
                    observe(case.case_id, stage, "bootstrap", bootstrap),
                ]
            )
    return observations


def test_complete_ast_parity_report_for_repository_corpus():
    corpus = load_corpus(MANIFEST)
    report = build_parity_report(corpus, observations_for(corpus), stages=["ast"])
    assert report.complete
    assert report.matched == 12
    assert report.total == 12
    assert report.stage_counts() == {"ast": (12, 12)}
    assert report.mismatches() == ()
    encoded = canonical_report_json(report)
    assert json.loads(encoded)["complete"] is True
    summary = markdown_summary(report)
    assert "PASS: 12/12" in summary
    assert "| `ast` | 12 | 12 |" in summary


def test_parity_report_identifies_exact_mismatch():
    corpus = load_corpus(MANIFEST)
    report = build_parity_report(
        corpus,
        observations_for(corpus, mismatch=("expr-precedence", "ast")),
        stages=["ast"],
    )
    assert not report.complete
    assert report.matched == 11
    assert report.total == 12
    assert [(item.case_id, item.stage) for item in report.mismatches()] == [("expr-precedence", "ast")]
    summary = markdown_summary(report)
    assert "FAIL: 11/12" in summary
    assert "`expr-precedence` / `ast`" in summary


def test_report_can_select_multiple_stages():
    corpus = load_corpus(MANIFEST)
    stages = ("expressions", "ast")
    report = build_parity_report(corpus, observations_for(corpus, stages=stages), stages=stages)
    assert report.total == 24
    assert report.stage_counts() == {"ast": (12, 12), "expressions": (12, 12)}


@pytest.mark.parametrize(
    "case_id, stage, implementation",
    [
        ("", "ast", "reference"),
        ("case", "unknown", "reference"),
        ("case", "ast", "other"),
    ],
)
def test_invalid_observations_are_rejected(case_id, stage, implementation):
    with pytest.raises(ParityContractError):
        observe(case_id, stage, implementation, {})


def test_missing_observations_are_rejected():
    corpus = parse_corpus(minimal_data())
    only_reference = [observe("simple-expression", "ast", "reference", {})]
    with pytest.raises(ParityContractError, match="missing observations"):
        build_parity_report(corpus, only_reference, stages=["ast"])


def test_duplicate_observations_are_rejected():
    corpus = parse_corpus(minimal_data())
    duplicate = observe("simple-expression", "ast", "reference", {})
    observations = [duplicate, duplicate, observe("simple-expression", "ast", "bootstrap", {})]
    with pytest.raises(ParityContractError, match="duplicate observation"):
        build_parity_report(corpus, observations, stages=["ast"])


def test_extra_observations_are_rejected():
    corpus = parse_corpus(minimal_data())
    observations = observations_for(corpus)
    observations.extend(
        [
            observe("unknown", "ast", "reference", {}),
            observe("unknown", "ast", "bootstrap", {}),
        ]
    )
    with pytest.raises(ParityContractError, match="do not belong"):
        build_parity_report(corpus, observations, stages=["ast"])


def test_unknown_selected_stage_is_rejected():
    corpus = parse_corpus(minimal_data())
    with pytest.raises(ParityContractError, match="unknown stage"):
        build_parity_report(corpus, [], stages=["backend"])


def test_ast_fingerprints_ignore_mapping_order_but_preserve_semantics():
    records = [
        (31, 0, 1, -1, -1),
        (31, 2, 1, -1, -1),
        (50, 0, 3, 0, 1),
    ]
    ast = lower_expression_ast(records)
    encoded = canonical_ast_json(ast)
    assert canonical_digest(encoded) == canonical_digest(canonical_ast_json(ast))
    changed = lower_expression_ast([(31, 0, 1, -1, -1)])
    assert canonical_digest(encoded) != canonical_digest(canonical_ast_json(changed))
