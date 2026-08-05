# Bootstrap corpus and parity reporting

Merit's replacement compiler is judged by differential evidence, not by whether it can compile a demonstration program. The versioned corpus and parity modules make that evidence explicit and machine-readable.

## Corpus contract

`tests/project/bootstrap_corpus_v1.json` is loaded through `merit.bootstrap.corpus`.

Each case has:

- a stable `id`
- a `kind` of `source` or `expression`
- exact source `text`
- an ordered list of stages to `compare`

The loader rejects duplicate identifiers, unknown stages, empty fields, AST gates without expression gates, expression cases without expression comparison, and source cases without token comparison.

Supported stage names are:

```text
tokens
syntax
diagnostics
expressions
ast
hir
mir
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
corpus = load_corpus("tests/project/bootstrap_corpus_v1.json")
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

## Intended next use

The Merit-native AST lowerer should emit canonical `bootstrap-ast-v1` data for the expression cases. The Python oracle and Merit implementation should each become observations, and the AST report must reach 100% before AST replacement is claimed.

The same mechanism then extends vertically to HIR, MIR, generated behavior, and stage-0/stage-1 comparison without inventing a separate test framework for every compiler phase.
