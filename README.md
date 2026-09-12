# Merit — Deterministic Systems Language

<p align="center">
  <img src="images/MeritLogoText.png" alt="Merit language logo" width="760">
</p>

Merit is a native compiled language experiment centered on deterministic semantics, exact numerics, ownership, explicit allocation, contracts, stable layouts, capability-specific hazardous operations, and C interoperability.

## Programming manual

Start with the [`docs/manual`](docs/manual/README.md) programming manual for user-facing language guidance, including ownership/borrowing, traits/generics, capabilities, and contracts.

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

The completed `v0.1.0-alpha.1` release is followed by the
`v0.1.0-alpha.2` release candidate. The authoritative GitHub Local Gate runs
clean Ubuntu and native-Windows corpus, replacement-acceptance,
reproducibility, and full validation. Exact counts remain checkpoint evidence
rather than a frozen README promise.

## Current replacement checkpoint

The Python-hosted compiler remains the independent semantic oracle. The trusted
Merit-native production compiler carries source-backed resolved functions with
contracts, ownership/control-flow metadata, capability identities, and source
provenance.

Supported native-resolved functions are serialized into versioned snapshots; multiple functions from one source unit are framed in `resolved-source-function-bundle-v2`, which carries their shared effective source once. Prepared replacement projects validate source digests, reconstruct canonical replacement MIR, emit deterministic C, and compile native executables without falling back to Python semantics.

The concrete native driver covers M1-M9: the complete accepted/rejected Alpha.1
corpus, all ten acceptance applications, default production-path cutover, and
clean stage reproducibility. PR #115 closed the trust gate with authoritative
Ubuntu and native-Windows evidence. M10 is the final release audit; Alpha.2
awaits final validation, manual merge, and tagging. See `ALPHA2_CLOSURE.md`.

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

Both compiler paths preserve concrete-before-MIR monomorphization and the same
documented semantic, ownership, and backend contracts rather than defining
parallel languages.

## CLI

```bash
merit check program.mrt
merit verify program.mrt
merit layout program.mrt
merit audit program.mrt
merit-project check PATH --replacement-driver EXECUTABLE
merit-project build PATH --replacement-driver EXECUTABLE
merit-project run PATH --replacement-driver EXECUTABLE
merit-project layout PATH --compiler reference
merit-project audit PATH --compiler reference
merit-project prepare-replacement PATH --replacement-driver EXECUTABLE
merit-project verify PATH --compiler reference
```

`merit-project` selects replacement compilation by default. It discovers the native frontend from `--replacement-driver`, `MERIT_REPLACEMENT_DRIVER`, or `merit-replacement-frontend` on `PATH`, and prepares fresh native-resolved artifacts before compiling. Existing prepared artifacts may still be consumed without rediscovery. Replacement mode is deliberately fail-closed and never silently uses Python semantics. `verify`, `layout`, and `audit` are reference/oracle tools and therefore require explicit `--compiler reference`. The single-file `merit` interface remains the explicitly documented independent reference compiler; it is not the normal production compiler path.

---

The previous release README is retained as `README.previous.md` for historical detail.
