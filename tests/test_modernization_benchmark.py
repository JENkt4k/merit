from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "modernization"
RUNNER = BENCHMARK / "run_reference.py"
CORPUS = BENCHMARK / "transaction_corpus.json"
EXPECTED_DIGEST = "bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d"


def _runner():
    spec = importlib.util.spec_from_file_location("modernization_reference", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_modernization_corpus_has_stable_semantic_digest_and_final_state():
    module = _runner()
    data = module.load_corpus(CORPUS)
    result = module.execute(data)

    assert result["transaction_count"] == 10
    assert result["committed"] == 3
    assert result["rejected"] == 7
    assert result["outcome_sha256"] == EXPECTED_DIGEST
    assert result["final_accounts"] == [
        {"id": 1001001, "balance_minor": 112700, "last_sequence": 43},
        {"id": 2002002, "balance_minor": 21075, "last_sequence": 43},
        {"id": 3003003, "balance_minor": 3750, "last_sequence": 42},
        {"id": 4004004, "balance_minor": 999999999999999950, "last_sequence": 7},
    ]


def test_rejected_transactions_do_not_mutate_state():
    module = _runner()
    data = module.load_corpus(CORPUS)
    prefix = dict(data)
    prefix["transactions"] = data["transactions"][:1]
    after_commit = module.execute(prefix)["final_accounts"]

    through_rejections = dict(data)
    through_rejections["transactions"] = data["transactions"][:7]
    after_rejections = module.execute(through_rejections)["final_accounts"]
    assert after_rejections == after_commit


def test_corpus_uses_integer_minor_units_not_host_floating_point():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    for account in data["accounts"]:
        assert type(account["balance_minor"]) is int
    for transaction in data["transactions"]:
        assert type(transaction["amount_minor"]) is int
