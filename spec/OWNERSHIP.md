# Ownership and borrowing in alpha.3

Alpha.3 implements the first executable ownership subset.

## Borrowed returns

Function signatures may spell borrowed results explicitly:

```merit
fn view(borrow value: Value) -> borrow Value { return value; }
fn edit(borrow_mut value: Value) -> borrow_mut Value { return value; }
```

The current lifetime-analysis checkpoint validates that a borrowed result originates directly from a borrowed parameter and that a mutable result originates from a `borrow_mut` parameter. Otherwise-valid borrowed returns are rejected with `M5302` until caller lifetime tracking and matching pointer lowering are implemented; they are not silently lowered as owned values.

## User-defined destructors

Structs may define one custom destructor:

```merit
stable("marker-v1") struct Marker { number: i32; }
destructor Marker { print(self.number); }
```

`self` is an implicit mutable borrow. The custom body runs exactly once before recursive field cleanup on explicit or implicit drop in both execution paths. The current parity-safe subset permits print and expression statements; ownership-changing statements are rejected with `M5502` until their cleanup interactions are specified.

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
- MIR receives implicit drops for remaining owned struct locals in reverse declaration order.
- Concrete types carry shared lifecycle metadata: ownership, copyability, drop requirement, semantic kind, and drop strategy.
- Function ownership effects identify consumed roots and explicit drops once for MIR and native cleanup lowering.
- Interpreter destruction recursively follows the same metadata for buffers, vectors, structs, and active enum payloads.
- Move and drop state retains its originating source span.
- Later use-after-move and use-after-drop diagnostics point to the invalid use and attach the original consumption site as a note.

## Deliberate limits

Loans are currently call-scoped. Stored borrows, returned borrows, subobject-disjointness, loops, branches, user destructors, and lifetime parameters are not implemented. These omissions are reported as alpha limits rather than modeled unsafely.
