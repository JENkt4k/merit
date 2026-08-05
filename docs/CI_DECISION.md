# CI Decision Record: Minimal Clean-Environment Gate

## Status

Accepted for bootstrap development.

## Context

Merit intentionally defers a broad hosted CI matrix until the non-Python compiler and its AST/HIR/MIR interfaces have survived multiple post-bootstrap releases. The project nevertheless benefits from one independent clean-environment check that confirms the established local gate is reproducible outside the maintainer's workstation.

## Decision

Use one GitHub Actions workflow with these constraints:

- standard Ubuntu runner only
- Python 3.11 only
- system C compiler only
- pull-request and manual triggers only
- obsolete runs cancelled through a concurrency group
- no deployment permissions
- no artifact uploads
- no platform or compiler matrix
- no release authority

The workflow installs the repository in editable development mode and invokes `scripts/ci.sh`. That script performs environment checks and delegates to `scripts/test.sh`, preserving one authoritative acceptance-project list.

## Consequences

Benefits:

- detects hidden local-environment dependencies
- gives pull requests an independent reproducibility signal
- does not duplicate compiler semantics or test selection
- has low maintenance and runner cost
- can be removed or expanded without affecting the compiler

Costs:

- adds some pull-request latency
- validates only one host environment
- does not prove portability or release readiness

## Deferred expansion conditions

Do not add an operating-system matrix, explicit GCC/Clang matrix, sanitizers, fuzzing, benchmarks, or release automation until all of the following are true:

1. Python is no longer required for normal compilation.
2. Typed AST, HIR, and MIR contracts have survived several implemented feature sets.
3. Multiple post-bootstrap releases have exercised those contracts.
4. Local release gates are mature and reproducible.
5. The additional matrix answers a concrete release or portability question.

## Non-authority

A green hosted workflow does not make the bootstrap compiler trusted or self-hosted. Trust remains defined by complete accepted/rejected corpus parity, stable intermediate-representation contracts, deterministic stage agreement, acceptance-project results, and repeated release evidence.
