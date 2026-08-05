# Local and GitHub Clean-Environment Gate

Merit's authoritative development gate remains the repository-local command:

```bash
./scripts/bootstrap.sh
./scripts/ci.sh
```

`./scripts/ci.sh` reports the active Python, pip, and C compiler, checks the installed Python dependency set, and then delegates to `./scripts/test.sh`.

`./scripts/test.sh` is the single source of truth for the current alpha gate. It runs the pytest suite and all interpreter/native acceptance verifiers, including filesystem and ledger verification in disposable directories.

## GitHub workflow scope

`.github/workflows/local-gate.yml` mirrors the same gate on one standard Ubuntu runner with Python 3.11 and the system C compiler.

It runs only for:

- pull requests
- manual `workflow_dispatch` requests

It deliberately does not run on every push.

Concurrency cancellation stops an obsolete run when a newer commit is pushed to the same pull request.

## Deliberate non-goals

This workflow is not a production release matrix. It does not add:

- multiple operating systems
- multiple Python versions
- separate GCC and Clang jobs
- sanitizers
- fuzzing
- benchmarks
- artifact uploads
- deployment or release automation

Those remain deferred until the non-Python compiler and its AST/HIR/MIR contracts have survived multiple post-bootstrap releases.

## Reproducing a failure

From a clean checkout with Python 3.11+ and a C compiler available as `cc`:

```bash
python -m pip install --upgrade pip
python -m pip install --no-build-isolation -e ".[dev]"
bash scripts/ci.sh
```

The gate should be debugged through the failing command shown in its output. Do not weaken or bypass an existing test to make the hosted runner green.

## Maintenance rule

When the local release gate changes, update `scripts/test.sh`; both local and GitHub execution will inherit the change. Avoid duplicating acceptance-project lists in workflow YAML.
