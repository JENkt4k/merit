# Contributing to Merit

Merit is in active bootstrap development. Contributions should advance one documented milestone while preserving the language's defining guarantees: deterministic semantics, exact numerics, ownership, explicit allocation, capability-specific hazards, contracts, stable layouts, and C interoperability.

## Before changing code

Read:

- `AGENTS.md`
- `ROADMAP.md`
- `STATUS.md`
- `BOOTSTRAP_STATUS.md`
- `LIMITATIONS.md`
- the relevant files under `spec/`

Do not broaden the language during the `v0.1.0-alpha.2` bootstrap milestone unless the roadmap explicitly changes.

## Setup

```bash
./scripts/bootstrap.sh
```

The project requires Python 3.11 or newer and a working C compiler available as `cc`.

## Validation

Run focused tests while developing, then run the complete clean-environment gate before proposing a change:

```bash
bash scripts/ci.sh
```

This command reports the active toolchain and delegates to `scripts/test.sh`, which is the authoritative list of tests and interpreter/native acceptance projects.

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

The GitHub Local Gate is intentionally a small clean-runner mirror of the local test command. It is not a broad platform matrix and should not become unrelated infrastructure work during bootstrap development.
