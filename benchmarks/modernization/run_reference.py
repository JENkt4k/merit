from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "transaction_corpus.json"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_corpus(path: Path = CORPUS) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "merit-modernization-transaction-v1":
        raise ValueError("unsupported benchmark schema")
    if data.get("minor_unit_scale") != 2:
        raise ValueError("v1 requires two decimal minor-unit places")
    ids = [account["id"] for account in data["accounts"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate account id")
    return data


def execute(data: dict) -> dict:
    maximum = int(data["max_balance_minor"])
    accounts = {
        int(item["id"]): {
            "balance_minor": int(item["balance_minor"]),
            "last_sequence": int(item["last_sequence"]),
        }
        for item in data["accounts"]
    }
    outcomes: list[dict] = []

    for tx in data["transactions"]:
        debit_id = int(tx["debit"])
        credit_id = int(tx["credit"])
        amount = int(tx["amount_minor"])
        sequence = int(tx["sequence"])
        debit = accounts.get(debit_id)
        credit = accounts.get(credit_id)

        if amount <= 0:
            result = "invalid_amount"
        elif debit_id == credit_id:
            result = "same_account"
        elif debit is None:
            result = "wrong_debit_account"
        elif credit is None:
            result = "wrong_credit_account"
        elif sequence <= debit["last_sequence"] or sequence <= credit["last_sequence"]:
            result = "duplicate_or_out_of_order"
        elif debit["balance_minor"] < amount:
            result = "insufficient_funds"
        elif credit["balance_minor"] > maximum - amount:
            result = "credit_overflow"
        else:
            debit["balance_minor"] -= amount
            credit["balance_minor"] += amount
            debit["last_sequence"] = sequence
            credit["last_sequence"] = sequence
            result = "committed"

        expected = tx.get("expect")
        if expected is not None and result != expected:
            raise AssertionError(f"{tx['id']}: expected {expected}, observed {result}")
        outcomes.append({"id": tx["id"], "result": result})

    final_accounts = [
        {
            "id": account_id,
            "balance_minor": accounts[account_id]["balance_minor"],
            "last_sequence": accounts[account_id]["last_sequence"],
        }
        for account_id in sorted(accounts)
    ]
    committed = sum(item["result"] == "committed" for item in outcomes)
    semantic = {
        "schema": data["schema"],
        "transaction_count": len(outcomes),
        "committed": committed,
        "rejected": len(outcomes) - committed,
        "outcomes": outcomes,
        "final_accounts": final_accounts,
    }
    semantic["outcome_sha256"] = hashlib.sha256(canonical_json(semantic)).hexdigest()
    return semantic


def run(path: Path = CORPUS) -> dict:
    raw = path.read_bytes()
    data = load_corpus(path)
    start = perf_counter_ns()
    semantic = execute(data)
    elapsed = perf_counter_ns() - start
    result = dict(semantic)
    result["corpus_sha256"] = hashlib.sha256(raw).hexdigest()
    result["elapsed_ns"] = elapsed
    result["transactions_per_second"] = (
        len(data["transactions"]) * 1_000_000_000 / elapsed if elapsed else None
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Merit modernization semantic reference")
    parser.add_argument("--json", action="store_true", help="emit compact machine-readable JSON")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args()
    result = run(args.corpus)
    if args.json:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(f"schema: {result['schema']}")
        print(f"transactions: {result['transaction_count']}")
        print(f"committed/rejected: {result['committed']}/{result['rejected']}")
        print(f"outcome sha256: {result['outcome_sha256']}")
        print(f"corpus sha256: {result['corpus_sha256']}")
        print(f"elapsed ns: {result['elapsed_ns']}")
        print(f"transactions/s: {result['transactions_per_second']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
