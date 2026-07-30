# Merit — Epoch III Generic Type Engine

<p align="center">
  <img src="images/MeritLogoText.png" alt="Merit language logo" width="760">
</p>

Merit is a native compiled language experiment centered on deterministic semantics, exact numerics, ownership, explicit allocation, contracts, stable layouts, capability-specific hazardous operations, and C interoperability.

This export is prepared for continued development in Codex. Start with:

- `AGENTS.md` — repository rules and invariants
- `CODEX_HANDOFF.md` — verified state and architecture
- `NEXT_WORK.md` — the next complete subsystem and acceptance gates
- `IMPORT_INTO_CODEX.md` — import instructions

## Baseline

```bash
./scripts/bootstrap.sh
./scripts/test.sh
```

At export time, the suite passes **50 tests** and verifies the Epoch II text pipeline, Epoch III binary packet parser, and generic-result acceptance project through both the interpreter and native C11 backend.

## Current checkpoint

Implemented generic syntax includes explicitly instantiated generic structs, payload enums, and functions with compiler-defined bounds:

```merit
struct Pair<T, U> {
    first: T;
    second: U;
}

enum Option<T> {
    Some(T),
    None
}

fn maximum<T: Ord>(left: T, right: T) -> T {
    if (left >= right) { return left; }
    return right;
}
```

Generic declarations are monomorphized into nominal declarations before the established semantic, ownership, MIR, interpreter, and C-backend pipeline.

## CLI

```bash
merit check program.mrt
merit verify program.mrt
merit-project check PATH
merit-project verify PATH
merit-project run PATH
```

The current trait checkpoint supports user-declared traits, coherent impls, and generic trait-bound dispatch. The next subsystem is allocator-backed `Vec<T>`; its exact scope is in `NEXT_WORK.md`.

---

The previous release README is retained as `README.previous.md` for historical detail.
