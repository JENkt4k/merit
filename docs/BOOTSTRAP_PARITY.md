# Bootstrap corpus and parity reporting

Merit's replacement compiler is judged by differential evidence, not by whether it can compile a demonstration program. The versioned corpus and parity modules make that evidence explicit and machine-readable.

## Corpus contract

`tests/project/bootstrap_corpus_v1.json` is adapted through `merit.bootstrap.repository_corpus` into the strict `bootstrap-corpus-v1` model in `merit.bootstrap.corpus`.

Each canonical case has:

- a stable `id`
- a `kind` of `source` or `expression`
- exact source `text`
- an ordered list of stages to `compare`

The strict loader rejects duplicate identifiers, unknown stages, empty fields, AST gates without expression gates, expression cases without expression comparison, and source cases without token comparison.

Supported stage names are:

```text
tokens
syntax
diagnostics
expressions
ast
hir
mir
interpreter
native
```

New stages should not be added casually. A stage name is a persistent comparison boundary and should first be specified in the bootstrap architecture.

## Canonical observations

`merit.bootstrap.parity.observe` converts a reference or bootstrap value into a deterministic observation. Structured values use compact, sorted JSON. Each observation exposes a SHA-256 digest of its canonical form.

Digests are used for reporting and compact storage; they do not replace inspectable canonical artifacts when a mismatch must be diagnosed.

## Reports

`build_parity_report` requires exactly one reference and one bootstrap observation for every selected case/stage gate. It rejects:

- missing sides
- duplicate observations
- observations for unknown cases or unrequested gates
- unknown implementations
- unknown stages

A report includes exact matched/total counts per stage and identifies every mismatching case/stage pair.

Example:

```python
corpus = load_repository_corpus("tests/project/bootstrap_corpus_v1.json")
report = build_parity_report(corpus, observations, stages=["ast"])
assert report.complete
```

The canonical JSON report is suitable for snapshots and later release evidence. `markdown_summary` is suitable for local logs or `$GITHUB_STEP_SUMMARY`.

## Coverage report

Run:

```bash
python scripts/bootstrap_report.py
```

or:

```bash
python scripts/bootstrap_report.py --json
```

This reports how many corpus cases currently participate in each compiler stage. A zero count is an explicit unimplemented gate, not an omitted metric.

## Executable AST parity gate

`tests/project/test_bootstrap_ast_parity_gate.py` is the first parity stage backed by real artifacts from both implementations rather than synthetic report inputs.

For every expression case in the repository corpus it:

1. obtains parser records from the independent Python expression oracle;
2. lowers those records through the canonical Python `bootstrap-ast-v1` contract;
3. runs one generated Merit probe over the complete expression corpus;
4. captures `AstNodeRecord` streams from the Merit interpreter and generated native executable;
5. reconstructs canonical ASTs through `merit.bootstrap.ast_parity`;
6. feeds the reference and bootstrap canonical artifacts into `build_parity_report`;
7. requires both interpreter and native reports to reach **12/12 AST parity**;
8. independently requires the native record streams to equal the interpreted streams.

The probe processes all expression cases in one temporary project so the gate does not require a separate compile for every corpus expression.

`merit.bootstrap.ast_parity.lower_native_ast_records` is the adapter from the Merit-native flat storage contract to canonical `AstNode`. It validates native spans, child ordering, known kinds, optional/required children, and grouping-provenance links before parity hashing.

## Next vertical use

AST now has an executable corpus-wide parity gate. The next vertical replacement boundary should apply the same pattern to typed HIR: choose a strictly supported AST subset, emit canonical `bootstrap-hir-v1` from the reference and replacement paths, and increase measured HIR corpus coverage without weakening the already-green AST gate.

The same mechanism then extends to MIR, generated behavior, and stage-0/stage-1 comparison without inventing a separate test framework for every compiler phase.
