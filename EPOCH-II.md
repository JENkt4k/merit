# Merit Epoch II — Application Language

Epoch II closes the application-language foundation begun in Application Foundation A and B.

## Delivered

- Project manifests and multi-file module graphs.
- Import-cycle, duplicate-symbol, visibility, and entry-module validation.
- Exact decimal, bounded integer, stable-layout struct, contract, capability, ownership, and borrowing foundations.
- Nominal payload enums, exhaustive matching, Result-style typed error propagation.
- UTF-8 string literals represented as immutable borrowed views.
- Explicit `Allocator` values and capability-gated allocation.
- Owned `Buffer` values with reserve, construction, push, length, indexed access, and deterministic destruction.
- Capability-gated native file reading.
- Move checking for owned buffers and mutable/shared borrow validation.
- CFG-shaped MIR with branch, switch, goto, and return terminators.
- C11 compilation, native execution, and interpreter/native differential verification.

## Acceptance application

`examples/projects/text_pipeline` is a multi-module native program. It allocates and mutates an owned buffer, passes it through a shared borrow, loops over its bytes, computes a checksum, prints UTF-8 text, and destroys the allocation deterministically.

Expected output:

```
Merit Epoch II
abc!
4
327
```

## Deliberate boundaries

Epoch II is an executable reference implementation, not yet a production compiler. Strings are immutable views; buffers are byte-oriented; allocators currently expose only the system allocator; file I/O reports runtime failure rather than a typed I/O enum; modules still merge into one C translation unit; and source spans are not yet retained through every semantic node.

Those boundaries define Epoch III rather than hidden incompleteness in this release.
