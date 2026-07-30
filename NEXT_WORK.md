# Next Work - Generic Collections

## Goal
Build allocator-backed `Vec<T>` on top of the now-usable user-visible trait checkpoint.

## Trait checkpoint now available
- User-declared traits with method signatures.
- `impl Trait for Type` blocks.
- Coherence rule: at most one implementation for a concrete trait/type pair within the program.
- Generic bounds resolved through user impls for concrete instantiations.
- Trait method calls inside instantiated generic functions lower to concrete impl methods.
- Interpreter/native verification through `examples/projects/trait_bounds`.

## Trait limits deliberately retained for the compact compiler
- No associated types, blanket impls, specialization, trait objects, or dynamic dispatch.
- Trait method signatures cannot yet express effects or required capabilities; impl methods using them are rejected.
- Trait-method lowering is still monomorphization-time source rewriting, guarded by ambiguity tests, not final AST-aware lowering.
- Generic templates and their trait impl evidence are still best kept in the same source unit until the compiler has a real project-wide generic expansion pass.

## Required collection features
1. Generic `Vec<T>` instantiated through the existing monomorphization pipeline.
2. Element move/drop behavior integrated into vector growth, indexing, removal, and destruction.
3. Generic `Option<T>` and `Result<T,E>` retained as normal library-style declarations.

## Deliberately deferred
- specialization
- associated types
- higher-kinded types
- blanket implementations unless coherence is formally defined
- trait objects/dynamic dispatch
- implicit generic type inference
- concurrency

## Suggested implementation order
1. Keep built-in operations available through compiler-supplied prelude implementations.
2. Generalize owned-vector runtime metadata for monomorphized element type, size, and drop behavior.
3. Lower each used `Vec<T>` to a concrete generated runtime representation.
4. Add vector APIs: `new`, `len`, `push`, `get`, `set`, `pop`, `drop`.
5. Add acceptance applications and C-header checks.

## Acceptance gates
The checkpoint is complete only when all of these pass:

### Positive
- `Vec<i64>` grows and preserves values.
- `Vec<Pair<i64,i32>>` stores generic structs.
- `Vec<Buffer>` moves owned buffers into the vector and destroys each exactly once.
- trait-bounds acceptance project remains green.
- generic `Option<Vec<i64>>` and `Result<Vec<i64>, Error>` compile and execute.
- interpreter and native output match for all acceptance programs.

### Negative
- duplicate trait impl remains rejected.
- missing trait impl remains rejected at generic instantiation.
- pushing an owned value and then using the moved source rejected.
- copying `Vec<T>` rejected.
- use-after-drop rejected.
- immutable vector mutation rejected.
- capability-free allocation rejected.

### Regression
- all existing tests remain green.
- simple examples, text pipeline, binary packet, generic result, and trait bounds projects still verify natively.

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
