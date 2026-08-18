# Merit — Deterministic Systems Language

<p align="center">
  <img src="images/MeritLogoText.png" alt="Merit language logo" width="760">
</p>

Merit is a native compiled language experiment centered on deterministic semantics, exact numerics, ownership, explicit allocation, contracts, stable layouts, capability-specific hazardous operations, and C interoperability.

## Design philosophy and rationale

Merit is being designed for **semantic longevity**: program meaning and language guarantees should remain stable while compiler algorithms, proof machinery, optimizers, code generators, and hardware targets remain free to evolve.

- [`docs/philosophy/SEMANTIC_LONGEVITY.md`](docs/philosophy/SEMANTIC_LONGEVITY.md) — the long-term rule: **freeze meaning, evolve implementation**.
- [`docs/philosophy/DESIGN_PRINCIPLES.md`](docs/philosophy/DESIGN_PRINCIPLES.md) — engineering criteria for deciding what belongs in Merit's permanent language surface.
- [`docs/rationale/LANGUAGE_STRATEGY.md`](docs/rationale/LANGUAGE_STRATEGY.md) — lessons Merit draws from COBOL, C, C++, Java, C#, Rust, Ada/SPARK, Fortran, and functional/ML-family languages.
- [`docs/migration/COBOL_MODERNIZATION.md`](docs/migration/COBOL_MODERNIZATION.md) — why COBOL modernization is difficult, what the current financial/copybook examples demonstrate, and how Merit separates enduring business semantics from legacy physical representation.

These documents describe design goals and constraints. Claims about performance, migration cost, productivity, or defect reduction should be supported by benchmarks and real migration evidence rather than inferred from the philosophy alone.

For continued development, start with:

- `AGENTS.md` — repository rules, invariants, and development loop
- `STATUS.md` — current project and replacement-compiler state
- `ROADMAP.md` — active critical path and later work
- `BOOTSTRAP_STATUS.md` — detailed replacement-compiler checkpoint
- `CODEX_HANDOFF.md` — accumulated implementation history and architecture
- `LIMITATIONS.md` — deliberately unsupported first-alpha behavior

## Baseline

```bash
./scripts/bootstrap.sh
./scripts/test.sh
bash scripts/ci.sh
```

The completed `v0.1.0-alpha.1` release gate is followed by `v0.1.0-alpha.2` replacement-compiler development. The authoritative GitHub Local Gate performs the clean Ubuntu/Python 3.11/system-C gate plus a focused Windows/MSYS2 UCRT64 GCC native smoke. Exact historical test counts belong in checkpoint evidence rather than this README because the suite changes continuously.

## Current replacement checkpoint

The Python-hosted alpha compiler remains the independent semantic oracle, but it is no longer the only path represented in the repository. The Merit-native replacement work has progressed from lexer/parser/AST/HIR fixtures into source-backed resolved functions carrying contracts, ownership/control-flow metadata, capability identities, and source provenance.

Supported native-resolved functions are serialized into versioned snapshots; multiple functions from one source unit are framed in `resolved-source-function-bundle-v1`. Prepared replacement projects validate source digests, reconstruct canonical replacement MIR, emit deterministic C, and compile native executables without falling back to Python semantics.

`merit-project prepare-replacement --replacement-driver EXECUTABLE` now defines the production frontend seam. The next critical milestone is to attach the concrete Merit-native source-unit frontend executable behind that boundary and prove the entire source-unit-to-native-executable path end to end. See `STATUS.md`, `ROADMAP.md`, and `BOOTSTRAP_STATUS.md`.

## Established language surface

The stable alpha reference implementation includes exact fixed-scale decimals, bounded/checked integers, ownership and deterministic destruction, explicit allocation, contracts, capability auditing, stable layouts/C interoperability, multi-module projects, payload enums and typed propagation, strings and owned buffers, coherent traits, explicitly instantiated generics, generic `Vec<T>` collections, filesystem capabilities, structured source diagnostics, and interpreter/native differential verification within the documented limits.

Generic syntax includes explicitly instantiated generic structs, payload enums, and functions with compiler-defined bounds:

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

The reference compiler currently monomorphizes generic declarations before its established semantic, ownership, MIR, interpreter, and C-backend pipeline. Replacing that implementation path must preserve the same documented meaning rather than inventing parallel semantics.

## CLI

```bash
merit check program.mrt
merit verify program.mrt
merit layout program.mrt
merit audit program.mrt
merit-project check PATH
merit-project verify PATH
merit-project run PATH
merit-project layout PATH
merit-project audit PATH
merit-project prepare-replacement PATH --replacement-driver EXECUTABLE
merit-project build PATH --compiler replacement
merit-project run PATH --compiler replacement
```

Replacement mode is deliberately fail-closed. It consumes prepared native-resolved artifacts for the supported replacement subset and does not silently use the Python reference compiler when replacement semantics are unavailable.

---

The previous release README is retained as `README.previous.md` for historical detail.
