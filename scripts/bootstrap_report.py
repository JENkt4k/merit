#!/usr/bin/env python3
"""Print deterministic bootstrap corpus coverage for local and hosted review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from merit.bootstrap.corpus import KNOWN_STAGES
from merit.bootstrap.repository_corpus import load_repository_corpus


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/project/bootstrap_corpus_v1.json"


def report_data(manifest: Path) -> dict[str, object]:
    corpus = load_repository_corpus(manifest)
    return {
        "schema": corpus.schema,
        "cases": len(corpus.cases),
        "kinds": {
            "expression": len(corpus.by_kind("expression")),
            "source": len(corpus.by_kind("source")),
        },
        "stages": {stage: len(corpus.for_stage(stage)) for stage in sorted(KNOWN_STAGES)},
    }


def markdown(data: dict[str, object]) -> str:
    kinds = data["kinds"]
    stages = data["stages"]
    assert isinstance(kinds, dict)
    assert isinstance(stages, dict)
    lines = [
        "## Bootstrap corpus coverage",
        "",
        f"Schema: `{data['schema']}`  ",
        f"Cases: **{data['cases']}** ({kinds['source']} source, {kinds['expression']} expression)",
        "",
        "| Stage | Cases |",
        "|---|---:|",
    ]
    for stage, count in stages.items():
        lines.append(f"| `{stage}` | {count} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    data = report_data(args.manifest)
    if args.as_json:
        print(json.dumps(data, sort_keys=True, separators=(",", ":")))
    else:
        print(markdown(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
