# Ownership and borrowing in alpha.3

Alpha.3 implements the first executable ownership subset.

## Borrowed returns

Function signatures may spell borrowed results explicitly:

```merit
fn view(borrow value: Value) -> borrow Value { return value; }
fn edit(borrow_mut value: Value) -> borrow_mut Value { return value; }
```

Borrowed results must originate from one consistent borrowed parameter, and mutable results require a `borrow_mut` origin. Callers may use returned borrows ephemerally for field access or pass them onward to a compatible borrow parameter. Mutable results support direct field assignment and owned-field replacement. The interpreter preserves object identity and native C lowers the result as a pointer. Returned borrows cannot be stored in owned bindings, passed by value, or escalated from shared to mutable access.

Generated C signatures preserve mutability: shared borrow parameters and results are `const T *`, while mutable borrows are `T *`.
Postconditions observe borrowed `result` through the same alias/pointer semantics in both execution paths.

## User-defined destructors

Structs may define one custom destructor:

```merit
stable("marker-v1") struct Marker { number: i32; }
destructor Marker { print(self.number); }
```

`self` is an implicit mutable borrow. The custom body runs exactly once before recursive field cleanup on explicit or implicit drop in both execution paths. The parity-safe subset permits printing, expressions, copy-field assignment, and structured `if`/`while` control flow. Ownership- or capability-changing statements remain rejected until their cleanup interactions are specified.

## Rules implemented

- Stable struct values are non-copy values.
- Passing a struct to a `value` parameter moves it.
- Assigning a struct variable to another variable moves it.
- A moved value cannot be read, assigned, borrowed, or dropped.
- `borrow` creates a shared call-scoped loan.
- `borrow_mut` creates an exclusive call-scoped loan and requires a mutable binding.
- The same root binding cannot be passed to a call through `borrow_mut` and any other loan simultaneously.
- Borrowed parameters cannot be explicitly dropped.
- `drop(name)` consumes an owned local.
- `replace(target, replacement)` evaluates the replacement once, drops the previous value in mutable addressable owned storage, installs the replacement, and consumes its source.
- Replacement accepts mutable locals, fields rooted in mutable aggregates, and mutable borrowed parameters.
- `vec_replace<T>(vector, index, replacement)` performs the same operation for an owned vector element after checked indexing.
- Native and interpreted replacement materialize a side-effecting target location once before drop/install; borrowed target calls are never repeated.
- Native copy assignment materializes the value before its target address, matching interpreted side-effect order.
- `allocator_compatible(left, right)` reports whether storage allocated by one provider may be transferred to and released by the other. Compatibility is provider identity in the current runtime: system is compatible with system, portable with portable, and the two providers are not interchangeable.
- Future zero-copy collection transfer and merge operations must reject incompatible allocators before moving elements or storage. Element-wise moves that allocate fresh destination storage may cross allocator providers because each allocation remains paired with its originating provider.
- `vec_transfer<T>(destination, source)` is the zero-copy transfer primitive. Both vectors must be distinct mutable bindings, the destination must be empty, and their allocators must be compatible. It steals the source allocation, leaves the source valid and empty, and transfers every owned-element destruction obligation without running a destructor during the transfer.
- `vec_allocator<T>(vector)` returns the retained allocator identity so transfer compatibility can be checked before attempting the operation.
- `Buffer` retains its allocator as part of its 32-byte runtime layout. Growth, filesystem-populated buffers, and destruction dispatch through that provider; `buffer_allocator(buffer)` exposes the retained identity.
- Legacy `I64Vec` follows the same 32-byte allocator-retaining contract and exposes `i64vec_allocator(vector)`.
- `buffer_push`, `i64vec_push`, and `vec_push<T>` require the lexical `allocate` capability because they may grow storage. Reserved capacity does not grant authority for later allocation attempts.
- Vectors may contain vectors. Moving an inner vector into an outer vector transfers its storage and recursive drop obligation; popping it transfers that obligation back to the destination binding.
- MIR receives implicit drops for remaining owned struct locals in reverse declaration order.
- Concrete types carry shared lifecycle metadata: ownership, copyability, drop requirement, semantic kind, and drop strategy.
- Function ownership effects identify consumed roots and explicit drops once for MIR and native cleanup lowering.
- Interpreter destruction recursively follows the same metadata for buffers, vectors, structs, and active enum payloads.
- Move and drop state retains its originating source span.
- Later use-after-move and use-after-drop diagnostics point to the invalid use and attach the original consumption site as a note.

## Deliberate limits

Loans are call-scoped except for validated ephemeral returned-borrow propagation. Stored borrows, subobject-disjointness, lifetime parameters, and ownership-changing destructor bodies are not implemented. These omissions are reported as alpha limits rather than modeled unsafely.
