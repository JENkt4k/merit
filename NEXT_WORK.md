# Next Work - Generic Collections

## Goal
Complete allocator-backed `Vec<T>` on top of the now-usable user-visible trait checkpoint.

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
1. Compiler-supplied prelude shape for vector builtins.
2. Consolidated ownership/drop metadata for aggregates and collections.
3. Broader C-header checks for aggregate enum layout where target ABI assumptions are explicit.

## Collection checkpoint now available
- `Vec<i64>` type syntax expands through the existing monomorphization path.
- `Vec<Pair<i64,i32>>` stores generic structs by value.
- `Vec<Buffer>` moves owned buffers into the vector and destroys live elements on vector drop.
- Structs containing owned fields move their field sources and generate deterministic aggregate drop glue.
- Enums containing owned payloads move constructor payload sources and generate active-variant drop glue.
- Generic `Option<Vec<i64>>` and `Result<Vec<i64>, Error>` compile, execute, and verify natively.
- `Vec<OwnedStruct>` supports structs with owned fields through pop/drop semantics and generated element destructors.
- Generated C marks expected unused helpers and match bindings so project verification output stays signal-focused.
- Generated headers emit static layout assertions for every concrete `Vec<T>`.
- Generic-style vector intrinsic calls such as `vec_new<i64>` and `vec_pop<OwnedText>` lower to concrete monomorphized vector operations.
- `vec_new__T`, `vec_push__T`, `vec_len__T`, `vec_get__T`, `vec_set__T`, `vec_pop__T`, and `vec_drop__T` are available for concrete `T`.
- `vec_get__Buffer` is rejected because it would copy an owned element; `vec_pop__Buffer` is the move-out operation.
- Vectors are owned values: copying/move-after-use is rejected.
- Allocation requires the `allocate` capability.
- Mutation requires a mutable vector binding.
- Interpreter/native verification through `examples/projects/generic_collections`.

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
2. Consolidate ownership/drop metadata into a typed semantic table instead of ad hoc predicates.
3. Add broader C-header checks for aggregate enum layout where target ABI assumptions are explicit.
4. Move generic vector intrinsic lowering from source normalization into typed call resolution.

## Acceptance gates
The checkpoint is complete only when all of these pass:

### Positive
- `Vec<i64>` grows and preserves values.
- `Vec<Pair<i64,i32>>` stores generic structs.
- `Vec<Buffer>` moves owned buffers into the vector and destroys each live element exactly once.
- structs with owned fields move sources into the struct and drop owned fields exactly once.
- enums with owned payloads move sources into active variants and drop active payloads exactly once.
- vectors of structs with owned fields drop all live elements exactly once.
- trait-bounds acceptance project remains green.
- generic `Option<Vec<i64>>` and `Result<Vec<i64>, Error>` compile and execute.
- interpreter and native output match for all acceptance programs.

### Negative
- duplicate trait impl remains rejected.
- missing trait impl remains rejected at generic instantiation.
- pushing an owned value and then using the moved source rejected.
- copying an owned vector element with `vec_get__Buffer` rejected.
- using an owned source after moving it into a struct field rejected.
- using an owned source after moving it into an enum payload rejected.
- using an owned enum subject after match rejected.
- copying an owned struct element with `vec_get__OwnedText` rejected.
- copying `Vec<T>` rejected.
- use-after-drop rejected.
- immutable vector mutation rejected.
- capability-free allocation rejected.

### Regression
- all existing tests remain green.
- simple examples, text pipeline, binary packet, generic result, trait bounds, and generic collections projects still verify natively without expected helper-warning noise.
- generated `Vec<T>` headers assert pointer/length/capacity layout at C compile time.

## Recommended acceptance project
Create `examples/projects/generic_collections/` with modules for:
- domain types
- trait implementations
- generic vector operations
- entry point

Expected demonstration:
- allocate a `Vec<Buffer>`
- insert multiple owned strings
- pop an owned string back out
- inspect owned data before explicit drop
- wrap owned data in a struct and drop the aggregate
- move vectors through `Option` and `Result` payloads
- store owned structs in vectors and move them back out with `pop`
- destroy all resources exactly once
