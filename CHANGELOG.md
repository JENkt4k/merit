# Changelog

## Epoch III — Call and control-flow accessor checkpoint

- Added typed accessors for calls, generic arguments, fields, constructors, binary expressions, and control flow.
- Migrated call resolution to the typed semantic view.
- Migrated checker, interpreter, and MIR branch/match paths to named operands.
- Added call and control-flow accessor coverage.
- Increased the regression suite from 170 to 171 tests.

## Epoch III — Ownership-sensitive node accessor checkpoint

- Added named typed accessors for bindings, initializers, assignment/replacement operands, statement expressions, and drops.
- Migrated ownership-sensitive checker and shared analysis paths off positional operands.
- Migrated corresponding interpreter and C lowering paths while preserving replacement ordering.
- Added semantic accessor and replacement operand coverage.
- Increased the regression suite from 169 to 170 tests.

## Epoch III — Typed backend-dispatch checkpoint

- Migrated MIR control-flow dispatch to `SemanticNodeView`.
- Migrated interpreter statement and expression dispatch to the typed boundary.
- Migrated C statement, expression-type, and expression dispatch to the typed boundary.
- Preserved all interpreter/native behavior and the 169-test baseline.

## Epoch III — Typed semantic-node adapter checkpoint

- Added a typed semantic-node view with kind, operand, span, and related-provenance access.
- Added `Program.node()` as the compatibility boundary for tuple-backed nodes.
- Migrated checker and shared ownership analysis dispatch to the typed interface.
- Preserved interpreter and native backend behavior behind the compatibility representation.
- Increased the regression suite from 168 to 169 tests.

## Epoch III — Generic expansion diagnostics checkpoint

- Added source locations to generic arity and trait-bound expansion errors.
- Preserved structured expansion errors through merged-project loading.
- Remapped project expansion failures to the concrete calling unit.
- Added single-source and cross-project expansion diagnostic coverage.
- Increased the regression suite from 165 to 168 tests.

## Epoch III — Declaration diagnostics checkpoint

- Preserved spans for type, field, trait, implementation, and function declarations.
- Added precise locations to duplicate, unknown-type, numeric-policy, trait-signature, and declaration capability errors.
- Unwrapped compiler errors raised by AST transformation for consistent structured rendering.
- Added four declaration diagnostic regression cases.
- Increased the regression suite from 161 to 165 tests.

## Epoch III — Cross-project generic provenance checkpoint

- Recorded concrete instantiation locations for generated generic semantic nodes.
- Remapped template and related instantiation spans to their owning project units.
- Rendered related notes from their own source files.
- Preserved source lines while preprocessing module and import declarations.
- Added a cross-module template/instantiation diagnostic regression test.
- Increased the regression suite from 160 to 161 tests.

## Epoch III — Local generic source-map checkpoint

- Preserved original line structure while extracting generic templates.
- Mapped semantic nodes in monomorphized bodies back to their template lines.
- Added diagnostics for generated-body failures and for ordinary declarations following templates.
- Increased the regression suite from 158 to 160 tests.

## Epoch III — Broad semantic diagnostics checkpoint

- Preserved spans for literals, constructors, calls, arithmetic, declarations, assignments, replacement, returns, capability regions, and control flow.
- Attached actionable primary locations to type, capability, replacement, exhaustiveness, constructor, field, and call diagnostics.
- Added rendered diagnostic regression tests for the principal semantic error families.
- Increased the regression suite from 154 to 158 tests.

## Epoch III — Project semantic diagnostics checkpoint

- Remapped merged-project semantic spans to their owning source units.
- Added structured `CompileError` rendering to every checking project workflow.
- Added the same structured semantic rendering to the single-source CLI.
- Added project check/build/run/verify/audit diagnostic regression coverage.
- Added multi-module ownership diagnostics that identify the correct non-entry file.

## Epoch III — Source-aware ownership diagnostics checkpoint

- Preserved source spans and source identity for variable, field, and drop nodes.
- Added move and drop origins to ownership state, including branch and loop merges.
- Added structured compile errors with primary spans and related notes.
- Rendered use-after-move and use-after-drop diagnostics with both source excerpts.
- Exposed ownership consumption sites in MIR.
- Added single-source, branch-flow, rendered diagnostic, MIR provenance, and project-merge tests.

## Epoch III — Typed semantic metadata checkpoint

- Added a cached concrete type table for ownership, copyability, drop requirements, semantic kinds, and drop strategies.
- Replaced vector ownership booleans with declarative element policies evaluated against type metadata.
- Added a shared function ownership-effects model for owned locals, consumed roots, and explicit drops.
- Migrated MIR and native epilogue cleanup to the shared ownership effects.
- Fixed duplicate native cleanup after direct owned local moves.
- Added metadata-driven recursive interpreter destruction for buffers, vectors, structs, and enums.
- Exposed type semantics in HIR and ownership effects in MIR.
- Added direct-move native parity, nested consuming-call, lifecycle metadata, and recursive destruction tests.

## Epoch III — Explicit owned replacement checkpoint

- Added `replace(target, replacement)` for mutable owned locals, owned fields, and mutable borrowed parameters.
- Defined replacement order as evaluate once, drop the displaced owner, then install and consume the replacement.
- Added checked `vec_replace<T>` for owned vector elements.
- Added conservative source/target alias rejection.
- Preserved replacement operations in MIR and excluded consumed replacement sources from implicit cleanup.
- Added interpreter/native parity and generated-C drop-order coverage.

## Epoch III — Filesystem capability acceptance checkpoint

- Added a project-level deterministic filesystem read/write acceptance application.
- Added interpreter/native parity coverage confined to test temporary directories.
- Added project audit assertions for allocation, filesystem-read, and filesystem-write policy classifications.
- Added project-derived negative tests for reads and writes outside their required capability regions.
- Updated the bootstrap environment to install declared development dependencies.
- Added an LF policy for executable shell scripts.

## Epoch II — Application Language

- Closed Application Foundation A and B into one application-language release.
- Added UTF-8 string literals and immutable `String` views.
- Added explicit `Allocator` values and `system_allocator()`.
- Added capability-gated `Buffer` allocation and string-to-buffer construction.
- Added owned byte-buffer mutation, length, indexed access, printing, and deterministic destruction.
- Added capability-gated native `file_read` runtime support.
- Extended move checking to owned buffers.
- Added automatic native cleanup for unreturned, non-explicitly-dropped buffers.
- Replaced inspection-only MIR with CFG-shaped blocks and branch/switch/goto/return terminators while retaining implicit-drop inspection compatibility.
- Added the multi-module text-pipeline acceptance application.
- Increased the test suite from 35 to 41 tests.

## Epoch III — Systems Core checkpoint

- Added immutable `ByteSlice` views over owned buffers.
- Added checked slice construction, length, and indexing.
- Added allocator-backed owned `I64Vec` collections.
- Added vector push, length, indexing, move checking, and deterministic destruction.
- Generalized owned-builtin cleanup beyond byte buffers.
- Added native C11 runtime support for slices and vectors.
- Added the multi-module binary packet acceptance project.
- Added systems-core ownership, type-checking, bounds, and native differential tests.
- Test suite increased from 41 to 45 tests.

## Epoch III — Generic Type Engine checkpoint

- Added source-level generic structs, enums, and functions.
- Added explicit monomorphization into nominal Merit declarations.
- Added scoped generic variant syntax (`Option<i64>::Some`).
- Added generic arity diagnostics.
- Added built-in `Copy`, `Eq`, `Ord`, and `Display` bound enforcement.
- Added generic `Option<T>` and `Result<T, E>` acceptance coverage.
- Added the `generic_result` project.
- Increased the regression suite from 45 to 50 tests.
