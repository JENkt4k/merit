# Contributing to Merit

Merit is in active bootstrap development. Contributions should advance one documented milestone while preserving the language's defining guarantees: deterministic semantics, exact numerics, ownership, explicit allocation, capability-specific hazards, contracts, stable layouts, and C interoperability.

## Before changing code

Read:

- `AGENTS.md`
- `docs/DEVELOPMENT_GATES.md`
- `ROADMAP.md`
- `STATUS.md`
- `BOOTSTRAP_STATUS.md`
- `LIMITATIONS.md`
- the relevant files under `spec/`

Do not broaden the language during the `v0.1.0-alpha.2` bootstrap milestone unless the roadmap explicitly changes.

## Setup

Install the editable development package in Python 3.11 or newer and verify the environment:

```text
python -m pip install --no-build-isolation -e ".[dev]"
python scripts/doctor.py
```

A working C compiler is required. The complete full-gate environment also uses Java and .NET. Native Windows development is supported through `scripts/activate-windows-dev.ps1` with MSYS2 UCRT64 GCC.

## Validation

Run focused tests while developing, then use the canonical cross-platform gates:

```text
python scripts/gate.py fast
python scripts/gate.py subsystem
python scripts/gate.py full --durations 50
```

Linux/WSL may use `bash scripts/ci.sh`; native Windows may use `.\scripts\test-windows.ps1 -Gate full -Durations 50`. These are thin wrappers around the same Python orchestration.

The full gate runs the complete pytest suite and all ten interpreter/native acceptance projects. GitHub Actions runs the same contract on Ubuntu and native Windows.

## Change discipline

A cohesive compiler change should normally include:

1. a syntax, semantic, or IR contract when behavior is new or changed
2. independent oracle cases where reference/bootstrap parity applies
3. positive tests
4. malformed-input or compile-fail tests
5. interpreter/native comparison where executable behavior changes
6. generated C inspection for evaluation order, ownership, cleanup, contracts, numerics, capabilities, or ABI-sensitive behavior
7. current status and metric updates

Do not weaken tests to obtain a green result. When the Python reference and Merit bootstrap compiler disagree, resolve the intended behavior from the specification and add a minimal regression case.

## Pull requests

Keep each pull request centered on one measurable gate. Describe:

- what changed
- why it is required
- which semantics or compiler stages are affected
- how the change was verified
- any deliberate limitations or follow-up work

The GitHub Local Gate is a clean-runner implementation of the same canonical validation contract used locally. Platform-specific setup may differ, but Windows, Linux/WSL, humans, and agents must not maintain separate semantic test policies.
