# Ownership and borrowing in alpha.3

Alpha.3 implements the first executable ownership subset.

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
- MIR receives implicit drops for remaining owned struct locals in reverse declaration order.

## Deliberate limits

Loans are currently call-scoped. Stored borrows, returned borrows, subobject-disjointness, loops, branches, user destructors, and lifetime parameters are not implemented. These omissions are reported as alpha limits rather than modeled unsafely.
