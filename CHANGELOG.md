# Changelog

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
