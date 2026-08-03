# Changelog

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
