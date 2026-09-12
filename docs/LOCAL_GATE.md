# Local and GitHub Clean-Environment Gate

Merit's authoritative development gate remains the repository-local command:

```bash
./scripts/bootstrap.sh
./scripts/ci.sh
```

`./scripts/ci.sh` reports the active Python, pip, and C compiler, checks the
installed dependency set, and delegates to `scripts/gate.py full`.

`scripts/gate.py` is the cross-platform source of truth. Its full gate runs the
pytest suite, all ten replacement acceptance projects, and explicit
reference/oracle acceptance verification, including filesystem and ledger work
in disposable directories. The dedicated `reproducibility` gate constructs and
compares compiler stages.

## GitHub workflow scope

`.github/workflows/local-gate.yml` runs the canonical Alpha.1 corpus, M7
replacement acceptance, M9 reproducibility, and full-gate contracts. Full and
reproducibility jobs run on both standard Ubuntu and native Windows/MSYS2
UCRT64 environments with Python 3.11.

It runs only for:

- pull requests
- manual `workflow_dispatch` requests

It deliberately does not run on every push.

Concurrency cancellation stops an obsolete run when a newer commit is pushed to the same pull request.

## Deliberate non-goals

This workflow is not a broad production release matrix. It does not add:

- multiple Python versions
- separate GCC and Clang jobs
- sanitizers
- fuzzing
- benchmarks
- deployment or release automation

Those remain post-Alpha.2 work unless a concrete portability or release defect
justifies expanding the gate.

## Reproducing a failure

From a clean checkout with Python 3.11+ and a C compiler available as `cc`:

```bash
python -m pip install --upgrade pip
python -m pip install --no-build-isolation -e ".[dev]"
bash scripts/ci.sh
```

The gate should be debugged through the failing command shown in its output. Do not weaken or bypass an existing test to make the hosted runner green.

## Maintenance rule

When the release gate changes, update `scripts/gate.py`; wrappers and hosted
jobs must continue to delegate to it. Avoid duplicating acceptance-project
inventories or semantic test policy in workflow YAML.
