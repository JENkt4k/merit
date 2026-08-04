# Codex Working Agreement — Merit

## Mission
Continue Merit as a deterministic systems language. Preserve exact numerics, explicit allocation, ownership, contracts, capability-gated hazardous operations, stable C interoperability, and interpreter/native semantic equivalence.

## Start here
1. Read `CODEX_HANDOFF.md`.
2. Read `ARCHITECTURE.md`, `EPOCH-III.md`, and the files under `spec/`.
3. Run `./scripts/bootstrap.sh` and then `./scripts/test.sh`.
4. Do not begin a feature unless the baseline is green.

## Non-negotiable invariants
- Every accepted program must have matching interpreter and native C behavior.
- Side-effecting expressions must be evaluated exactly once in generated C.
- Owned values cannot be copied implicitly.
- Moves, explicit drops, implicit drops, and early returns must never double-destroy resources.
- Allocation and other hazardous operations require the appropriate capability.
- Decimal arithmetic remains exact and its rounding policy explicit.
- Stable-layout declarations must preserve deterministic layout and generated C assertions.
- New syntax needs parser, semantic, ownership, MIR, interpreter, C backend, diagnostics, and tests.
- Prefer extending the existing monomorphization pipeline over creating a second execution path.

## Commands
```bash
./scripts/bootstrap.sh
./scripts/test.sh
merit-project verify examples/projects/generic_result
merit-project verify examples/projects/binary_packet
merit-project verify examples/projects/text_pipeline
```

## Current checkpoint
The **`v0.1.0-alpha.1` local release gate is complete**. The active target is **`v0.1.0-alpha.2`**, eliminating Python from the normal compiler path while retaining it as the reference oracle. `STATUS.md`, `ROADMAP.md`, `spec/BOOTSTRAP.md`, and `BOOTSTRAP_STATUS.md` define the active gates.

Keep reference, bootstrap, trusted, and self-hosted compiler stages distinct. Follow this pipeline without collapsing boundaries:

```text
Source -> Lexer -> Tokens -> CST -> AST -> HIR -> semantic/ownership/contracts/capabilities -> MIR -> deterministic C -> native compilation
```

The immediate order is typed statements, precedence-aware expressions, typed clause operands, deterministic recovery, explicit CST-to-AST lowering, AST, HIR, semantic checking, MIR, and only then C emission and stage equivalence. Do not broaden the language during bootstrap.
