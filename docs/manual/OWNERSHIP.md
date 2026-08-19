# Ownership and borrowing

Merit distinguishes copyable values from owned values that carry a destruction obligation. Ownership is deterministic: an owned value has one owner at a time, and moving it transfers both the value and the responsibility to destroy it.

## Moves

Passing an owned value to a `value` parameter, assigning it into another owned binding, returning it by value, or placing it into another owning container consumes the source.

After a move, using the old binding is an error.

```merit
fn consume(value: Resource) -> i32 {
    return 0;
}

let resource: Resource = make_resource();
let status: i32 = consume(resource);
// resource may not be used here: ownership moved into consume.
```

Value-mode owned parameters belong to the callee. If they are not moved onward or explicitly dropped, the function's normal cleanup owns their destruction.

## Explicit drop

`drop(name)` consumes an owned binding and runs its deterministic cleanup.

```merit
let value: Resource = make_resource();
drop(value);
```

Dropping twice or using the binding after the drop is rejected.

Owned locals introduced inside `if`, `while`, or match-arm scopes must be moved or explicitly dropped before leaving that scope in the current alpha. The compiler does not guess branch-local ownership cleanup.

## Shared borrowing

Use `borrow` when a function needs temporary read access without taking ownership.

```merit
fn inspect(borrow value: Resource) -> i32 {
    return value.code;
}
```

The owner remains responsible for destruction. A shared borrow does not transfer that obligation.

## Mutable borrowing

Use `borrow_mut` for temporary exclusive mutation. The source binding must be mutable.

```merit
fn reset(borrow_mut value: Counter) -> i32 {
    value.count = 0;
    return 0;
}
```

The same root cannot participate in an incompatible shared/mutable loan combination in one call.

## Borrowed returns

Functions may return a validated borrow:

```merit
fn view(borrow value: Value) -> borrow Value {
    return value;
}
```

The current alpha intentionally keeps returned borrows **ephemeral**. They may be used for immediate field access/mutation or passed onward to a compatible borrowed parameter, but they may not be stored as owned locals, fields, vector elements, enum payloads, or otherwise made to outlive the validated origin. Stored references and lifetime parameters are outside the current alpha.

## Replacement

`replace(target, replacement)` changes owned storage without leaking the previous value. The old value is destroyed and ownership of the replacement is transferred into the target.

For generic vectors, `vec_replace<T>` performs the same ownership-safe operation on an element.

## Containers and allocators

Owned values inside vectors carry their destruction obligations with them. Moving an inner vector into another owning container transfers its storage and recursive cleanup obligation.

Zero-copy `vec_transfer<T>(destination, source)` additionally requires allocator compatibility. Merit does not treat storage allocated by unrelated providers as interchangeable merely because the element types match.

## Why the rules are strict

Ownership errors are compile-time semantic errors rather than cleanup heuristics. This makes lifetime and destruction behavior stable across the interpreter, generated native code, and future replacement compilers.
