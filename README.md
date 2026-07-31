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

The current local gate runs the pytest suite plus native project verification for the text pipeline, binary packet parser, generic result, trait bounds, and generic collections acceptance projects.

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
merit layout program.mrt
merit-project check PATH
merit-project verify PATH
merit-project run PATH
merit-project layout PATH
```

The current systems checkpoint supports user-declared traits, coherent impls, generic trait-bound dispatch, allocator-backed `Vec<T>` support for scalars/generic structs/owned `Buffer` elements/owned structs, parsed generic-style vector intrinsic calls such as `vec_new<i64>`, compile-time `Vec<T>` and enum layout assertions, layout hash reporting for structs/generated vectors/enums, aggregate drop glue for structs with owned fields, and owned enum payloads for `Option<Vec<i64>>` / `Result<Vec<i64>, Error>` style code. Remaining collection work is scoped in `NEXT_WORK.md`.

---

The previous release README is retained as `README.previous.md` for historical detail.
