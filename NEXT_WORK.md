# Next Work — Traits and Generic Collections

## Goal
Replace the compiler-defined generic-bound checkpoint and fixed `I64Vec` abstraction with a coherent user-visible trait system and allocator-backed `Vec<T>`.

## Required language features
1. User-declared traits with method signatures.
2. `impl Trait for Type` blocks.
3. Coherence rule: at most one applicable implementation for a concrete trait/type pair within the program.
4. Generic bounds resolved through implementations rather than hard-coded type-name checks.
5. Generic `Vec<T>` instantiated through the existing monomorphization pipeline.
6. Element move/drop behavior integrated into vector growth, indexing, removal, and destruction.
7. Generic `Option<T>` and `Result<T,E>` retained as normal library-style declarations.

## Deliberately deferred
- specialization
- associated types
- higher-kinded types
- blanket implementations unless coherence is formally defined
- trait objects/dynamic dispatch
- implicit generic type inference
- concurrency

## Suggested implementation order
1. Add trait and impl AST nodes plus parser tests.
2. Build a trait registry during semantic setup.
3. Add duplicate/conflicting implementation diagnostics.
4. Resolve generic bounds against the registry.
5. Keep built-in operations available through compiler-supplied prelude implementations.
6. Generalize owned-vector runtime metadata for monomorphized element type, size, and drop behavior.
7. Lower each used `Vec<T>` to a concrete generated runtime representation.
8. Add vector APIs: `new`, `len`, `push`, `get`, `set`, `pop`, `drop`.
9. Add acceptance applications and C-header checks.

## Acceptance gates
The checkpoint is complete only when all of these pass:

### Positive
- `Vec<i64>` grows and preserves values.
- `Vec<Pair<i64,i32>>` stores generic structs.
- `Vec<Buffer>` moves owned buffers into the vector and destroys each exactly once.
- a generic function bounded by a user-defined trait compiles for a valid implementation.
- generic `Option<Vec<i64>>` and `Result<Vec<i64>, Error>` compile and execute.
- interpreter and native output match for all acceptance programs.

### Negative
- duplicate trait impl rejected.
- missing trait impl rejected at generic instantiation.
- pushing an owned value and then using the moved source rejected.
- copying `Vec<T>` rejected.
- use-after-drop rejected.
- immutable vector mutation rejected.
- capability-free allocation rejected.

### Regression
- all existing 50 tests remain green.
- simple examples, text pipeline, binary packet, and generic result projects still verify natively.

## Recommended acceptance project
Create `examples/projects/generic_collections/` with modules for:
- domain types
- trait implementations
- generic vector operations
- entry point

Expected demonstration:
- allocate a `Vec<Buffer>`
- insert multiple owned strings
- iterate or index them
- compute a deterministic checksum
- return a typed result
- destroy all resources exactly once
