---
name: Clean-environment gate failure
about: Track a reproducible failure in the minimal GitHub/local gate
labels: bug
---

## Failing revision

Commit or pull request:

## Failing command

Copy the exact command or acceptance verifier that failed.

## Environment

Include the Python, pip, and C compiler versions printed by `scripts/ci.sh`.

## Observed output

```text
paste the minimal relevant failure here
```

## Local reproduction

```bash
python -m pip install --no-build-isolation -e ".[dev]"
bash scripts/ci.sh
```

## Classification

- [ ] hidden environment dependency
- [ ] Python test regression
- [ ] generated-C compilation regression
- [ ] interpreter/native parity regression
- [ ] acceptance-project isolation regression
- [ ] packaging or installation regression
- [ ] unknown

Do not weaken or delete an existing test to resolve the failure. Record any intentional semantic change in the relevant specification first.
