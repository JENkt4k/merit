# Merit Roadmap

## Epoch I — Semantic Foundation — closed

Exact decimals, bounded values, contracts, capabilities, stable layouts, ownership experiments, borrowing, interpretation, C generation, native execution, and differential testing.

## Epoch II — Application Language — closed

Projects and modules, visibility, enums, exhaustive matching, typed propagation, strings, owned byte buffers, explicit system allocation, deterministic buffer cleanup, file-read runtime support, and CFG-shaped MIR.

## Epoch III — Systems Language

The next epoch is intentionally larger:

- Generic types and functions.
- Traits/interfaces with coherence rules.
- `Option<T>` and `Result<T,E>` as standard generic types.
- Slices with explicit lifetimes and returned/stored borrows.
- User-defined destructors and resource-owning structs.
- Multiple allocator implementations and allocator parameters.
- Typed file and operating-system errors.
- Separate module compilation and object caching.
- Qualified names and explicit namespace imports.
- Complete source spans and structured diagnostics.
- Optimization passes over MIR.
- Atomics, threads, mutexes, and channels only after ownership interactions are specified.
- A production compiler implementation plan, likely retaining Python as the semantic oracle.

Acceptance projects:

1. Binary protocol parser using slices and typed errors.
2. C-callable shared library with stable ABI.
3. Concurrent checksum/file-processing utility.
4. Allocator-pluggable collections library.

## Epoch IV — Scientific and Industrial Readiness

Deterministic floating-point policies, arrays and views, SIMD metadata, numerical libraries, fuzzing, compatibility tooling, formatter, LSP, package tooling, and multi-platform release engineering.
