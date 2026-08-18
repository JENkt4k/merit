# Merit Status

Status date: 2026-08-18

## Release target

The `v0.1.0-alpha.1` local release gate is complete. Package metadata uses the PEP 440 equivalent version `0.1.0a1`.

Development is on `v0.1.0-alpha.2`: remove Python from the normal compiler path without broadening the language. Python remains an independent semantic/diagnostic oracle until the replacement compiler qualifies as trusted.

The authoritative GitHub Local Gate currently covers a full clean Ubuntu/Python 3.11/system-C run plus a focused Windows/Python 3.11/MSYS2 UCRT64 GCC native smoke run. PR #76 passed Local Gate run 177 before merge.

## Proven alpha foundation

- Generated C evaluates sibling operands and arguments exactly once, left to right.
- Ownership, moves, drops, cleanup, interpreter frames, and C names use deterministic semantic binding IDs.
- Returned borrows are validated and ephemeral-only; stored references and lifetime parameters remain outside this alpha.
- Exact decimals, bounded integers, explicit allocation, capability-specific hazards, typed errors, stable layouts, shared-library builds, and interpreter/native equivalence are implemented for the documented alpha subset.
- The exact-decimal ledger application exercises multi-module typed errors, filesystem capabilities, explicit allocation, stable exports, and foreign ABI verification.
- Independent arbitrary-precision references cover decimal rounding policies and bounded arithmetic boundaries.

All seven ordered `v0.1.0-alpha.1` gates remain complete. No known semantic correctness blocker remains undocumented; deliberate exclusions remain recorded in `LIMITATIONS.md`.

## Active replacement-compiler state

The replacement effort has progressed beyond the early isolated lexer/parser/AST/HIR checkpoints. The repository now contains native source-backed function resolution that carries function bodies, contracts, instruction provenance, ownership bindings/effects, CFG records/placement, and capability identities into versioned resolved-source snapshots. Multiple resolved functions from one source unit are framed in a versioned `resolved-source-function-bundle-v1` bundle.

Those native-resolved artifacts feed the production replacement build boundary. Replacement builds consume prepared snapshots, reconstruct canonical replacement MIR, emit deterministic C, compile it, and refuse to fall back to the Python reference compiler. Project artifacts are source-digest checked so stale snapshots fail closed.

PR #75 established multi-function source-unit bundles. PR #76 replaced the arbitrary external command-vector producer seam with a first-class `NativeReplacementDriver` executable boundary: `merit-project prepare-replacement --replacement-driver EXECUTABLE` invokes exactly one driver executable per source unit. Python at this boundary is orchestration only: it supplies source text, validates transport/framing, records source identity, and atomically publishes artifacts; it does not parse or semantically lower target source.

## Current frontier

The immediate production frontier is to attach a concrete Merit-native source-unit frontend executable behind `NativeReplacementDriver` and prove the complete vertical path:

```text
Merit source unit
  -> native replacement frontend driver
  -> resolved multi-function bundle
  -> prepared replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
```

After that vertical path is real, expand replacement coverage toward the complete accepted alpha corpus, preserving fail-closed behavior for unsupported constructs and reference/interpreter/native differential evidence. Normal project compilation can move to the replacement path only when the covered semantic surface is sufficient and corpus parity is established.

## Trust boundary

Python remains the independent semantic and diagnostic reference oracle. The Merit-native replacement compiler is not yet trusted or self-hosted. Trust requires complete accepted/rejected corpus parity for the target alpha surface, stable typed stage contracts, deterministic stage agreement, and a clean release cycle. Self-hosting begins only after that trust gate and requires reproducible stage equivalence.

Do not describe early parser/HIR/MIR corpus counts as whole-language replacement percentages. The useful progress metric is vertical removal of Python semantic authority from real production compilation boundaries.
