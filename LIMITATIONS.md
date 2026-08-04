# Merit `v0.1.0-alpha.1` Limitations

These limits are deliberate and enforced. They are not promises of silently approximated behavior.

## Ownership and borrowing

- Returned borrows are ephemeral. They may support field access/mutation, compatible borrowed arguments, or validated borrowed-return relays, but cannot be stored.
- Reference-typed locals, general lifetime parameters, subobject-disjoint borrowing, and partial moves from owned fields are unavailable.
- Owned branch/loop/match locals and owned match payloads must be moved or explicitly dropped before leaving their lexical scope.
- `old(...)` accepts Copy values only. Owned contract snapshots are unavailable.
- Destructor bodies cannot move/drop owners or enter capability regions.

## Types and generics

- Generic arguments are explicit and monomorphization is presently source-rewrite based.
- Associated types, blanket implementations, specialization, trait objects, dynamic dispatch, higher-kinded types, and trait-method effects/capabilities are unavailable.
- Lossy numeric conversion and floating-point types are unavailable; no silent numeric loss is permitted.

## Compilation and runtime

- Projects merge into one generated C translation unit; the object cache is not dependency-granular.
- The production path is Python-hosted and lowers to C11. LLVM and self-hosted/replacement compilation are post-alpha work.
- System and portable allocator identities are distinct, but currently use the same host allocation primitives.
- There is no async, concurrency, networking, tensor runtime, package registry, formatter, or language server in this alpha.
- Hosted CI is intentionally deferred; the authoritative release gate is local and deterministic.
