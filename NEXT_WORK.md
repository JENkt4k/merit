# Next Work - Roadmap Status

## Goal
Advance the core Merit feature set in complete, testable epic slices while preserving interpreter/native parity.

## Original epic status
- Project-wide generic expansion and trait evidence: substantial checkpoint complete.
- Contracts and verification depth: active checkpoint complete in this slice.
- Capability model hardening: active checkpoint complete in this slice.
- Memory model polish: active checkpoint complete in this slice.
- Project-level filesystem capability acceptance: complete in this slice.

## Filesystem capability acceptance checkpoint now available
- A dedicated project writes and reads deterministic `MRT` bytes through `file_write` and `file_read`.
- Acceptance execution is confined to pytest or shell-created temporary directories.
- Interpreter and native output agree for project-level filesystem operations.
- Project audit output classifies allocation, filesystem reads, and filesystem writes with their review categories and lexical scope.
- Project-derived negative tests reject read and write calls outside the corresponding capability region.

## Trait checkpoint now available
- User-declared traits with method signatures.
- `impl Trait for Type` blocks.
- Coherence rule: at most one implementation for a concrete trait/type pair within the program.
- Generic bounds resolved through user impls for concrete instantiations.
- Trait method calls inside instantiated generic functions lower to concrete impl methods.
- Project-wide generic expansion supports templates, instantiation sites, and trait impl evidence split across imported modules.
- Project visibility checks cover generic template ownership, generic bounds, trait method signatures, and impl trait/target references.
- Interpreter/native verification through `examples/projects/trait_bounds`.

## Trait limits deliberately retained for the compact compiler
- No associated types, blanket impls, specialization, trait objects, or dynamic dispatch.
- Trait method signatures cannot yet express effects or required capabilities; impl methods using them are rejected.
- Trait-method lowering is still monomorphization-time source rewriting, guarded by ambiguity tests, not final AST-aware lowering.
- Project-wide generic expansion is still compact source-level monomorphization, not a final typed generic IR or incremental compilation model.

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
- Generated headers emit conservative static layout assertions for enum tag and payload placement.
- `merit layout` and `merit-project layout` report layout hashes for stable structs, generated vectors, and enums.
- Generated headers include layout hash identity comments for stable structs, generated vectors, and enums.
- Generic-style vector intrinsic calls such as `vec_new<i64>` and `vec_pop<OwnedText>` parse as typed `generic_call` nodes and resolve through semantic call handling.
- Vector acceptance tests and the generic collections example use generic-style vector intrinsic calls instead of concrete `vec_*__T` spelling.
- Vector intrinsic arity, return kind, receiver mode, allocation requirement, and owned-copy restrictions are centralized in one compiler table.
- Type ownership, drop requirement, and copyability are classified through shared semantic helpers used by checker, cleanup, MIR, and generated drop emission paths.
- `vec_new__T`, `vec_push__T`, `vec_len__T`, `vec_get__T`, `vec_set__T`, `vec_pop__T`, and `vec_drop__T` are available for concrete `T`.
- `vec_get__Buffer` is rejected because it would copy an owned element; `vec_pop__Buffer` is the move-out operation.
- Vectors are owned values: copying/move-after-use is rejected.
- Allocation requires the `allocate` capability.
- `merit audit` and `merit-project audit` report declared capabilities, capability policy requirements, capability sites, capability-bearing calls, and hazardous builtin/vector operations.
- Generated C marks capability regions with explicit begin/end audit comments.
- Mutation requires a mutable vector binding.
- Interpreter/native verification through `examples/projects/generic_collections`.

## Contract checkpoint now available
- `requires` and `ensures` expressions are type-checked as boolean/comparison contract conditions before execution/codegen.
- `old()` is legal only while checking postconditions.
- `old()` in preconditions and ordinary code is rejected during checking instead of surfacing later.
- Interpreter and generated native binaries agree on deterministic precondition failure behavior.
- Interpreter and generated native binaries agree on deterministic postcondition failure behavior.
- Native contract failures preserve distinct exit codes for precondition and postcondition failures.

## Capability checkpoint now available
- Builtin hazardous operation metadata covers allocation, filesystem read, and filesystem write classes.
- `file_write` is a distinct capability-gated hazardous operation.
- Unauthorized filesystem writes are rejected during checking.
- Authorized filesystem writes execute in both interpreter and generated native binaries.
- Audit output includes centralized capability policy metadata: hazard class, review category, and lexical scope.
- Audit requirements and observed hazardous operations carry consistent policy classifications.

## Memory model checkpoint now available
- Owned-source consumption is centralized across bindings, assignments, returns, struct construction, enum construction, vector value operations, builtin calls, and user-function calls.
- Moving an owned field out of an aggregate is rejected until partial-move/drop-state tracking exists.
- Passing an owned field to a consuming function is rejected.
- Returning an owned field from an aggregate is rejected.
- Constructing a new aggregate by moving an owned field out of another aggregate is rejected.
- Assignment into existing owned storage is rejected until explicit replace/drop semantics exist.

## Recommended next epic
Continue memory model polish:
- Extend the implemented local `replace(target, replacement)` operation to owned struct fields and other addressable owned storage.
- Add partial-move tracking only if the language commits to field-level ownership states.
- Improve diagnostics with move-origin notes once the checker carries source spans.

## Deliberately deferred
- specialization
- associated types
- higher-kinded types
- blanket implementations unless coherence is formally defined
- trait objects/dynamic dispatch
- implicit generic type inference
- concurrency

## Suggested implementation order
1. Design explicit replacement operations for owned storage.
2. Continue migrating checker/codegen decisions onto typed semantic metadata.
3. Continue removing duplicated aggregate/drop special cases as parser and AST support improve.

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
- hazardous builtin and vector operations appear in source/project audit output.

### Regression
- all existing tests remain green.
- simple examples, text pipeline, binary packet, generic result, trait bounds, and generic collections projects still verify natively without expected helper-warning noise.
- generated `Vec<T>` headers assert pointer/length/capacity layout at C compile time.
- generated enum headers assert tag offset and payload placement at C compile time.
- source and project layout commands report hashes for generated vectors and enums.
- contract precondition failures produce matching interpreter/native diagnostics.
- contract postcondition failures produce matching interpreter/native diagnostics.
- invalid contract expression types are rejected during checking.
- `old()` outside postconditions is rejected during checking.
- unauthorized `file_write` calls are rejected during checking.
- authorized `file_write` calls match in interpreter and native execution.
- audit output classifies allocation, filesystem read, and filesystem write hazards.
- owned field extraction into a new binding is rejected.
- owned field extraction into a consuming call is rejected.
- owned field extraction through aggregate construction or return is rejected.
- assignment into owned storage is rejected until replacement semantics exist.

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
