# Epoch III — Systems Language

## Systems Core checkpoint

This checkpoint begins Epoch III with the first reusable systems-programming substrate:

- `ByteSlice`: immutable, non-owning byte views into owned buffers.
- checked slice construction, length, and indexing.
- `I64Vec`: allocator-created, growable, owned integer vectors.
- vector mutation through exclusive borrows.
- deterministic vector destruction in explicit and implicit epilogues.
- move checking for vector ownership.
- native C11 runtime lowering for slices and vectors.
- a multi-module binary packet decoder acceptance application.

## Safety rules

- `buffer_slice` requires an addressable `Buffer` binding.
- slice ranges are checked at runtime in both interpreter and native code.
- vectors require the `allocate` capability.
- mutating a vector requires a mutable addressable binding.
- moving an `I64Vec` consumes the source binding.
- local vectors are destroyed deterministically unless moved, returned, or explicitly dropped.

## Acceptance project

`examples/projects/binary_packet` decodes a two-byte big-endian header, checksums a payload through slices, stores results in an owned vector, and verifies interpreter/native agreement.

Expected output:

```text
258
60
2
258
60
```

## Remaining Epoch III work

The generic type engine, user-defined traits with coherence checks, generic
`Option<T>`/`Result<T, E>`, typed I/O errors, ephemeral returned borrows,
custom destructors, generic vectors, and content-addressed object caching are
implemented and covered by interpreter/native acceptance tests.

Still open:

- stored reference values and explicit lifetime parameters
- subobject-disjoint borrowing
- ownership- or capability-changing destructor bodies
- per-module separate compilation and dependency-granular cache invalidation
- broader trait features deliberately deferred below
- production optimizer and LLVM lowering

## Generic type engine checkpoint

The second Epoch III checkpoint adds an explicit monomorphization layer before ordinary Merit semantic analysis.

Implemented:

- generic structs such as `Pair<T, U>`
- generic payload enums such as `Option<T>` and `Result<T, E>`
- explicitly instantiated generic functions
- nominally scoped generic enum variants using `Type<Args>::Variant`
- built-in generic bounds: `Copy`, `Eq`, `Ord`, and `Display`
- deterministic, reproducible symbol mangling
- reuse of the existing checker, ownership passes, MIR, interpreter, and C backend after expansion

Generic declarations are instantiated only for concrete applications present in the source. The expanded declarations remain ordinary nominal Merit types, so generic code does not create a parallel execution model.

Current constraints:

- type arguments must presently be explicit
- bounds support compiler-defined traits and coherent user-defined trait implementations
- project loading expands visible templates and concrete applications across imported modules
- monomorphization remains source rewriting rather than a typed generic IR
- nested generic vectors are supported; associated types and higher-kinded types are not
- trait method signatures cannot yet express effects or required capabilities
