# Enums, matching, and typed errors

## Nominal payload enums

```merit
enum MathError { Negative, TooLarge }
enum IntResult { Ok(i32), Err(MathError) }
```

Each variant has zero or one payload. Variant names must be unique across the current program in this prototype.

## Exhaustive matching

```merit
match (result) {
    Ok(value) => { print(value); }
    Err(error) => { print(0); }
}
```

All variants must appear exactly once. Payload variants require a binding; payload-free variants reject one. The subject is evaluated exactly once in generated C.

## Typed propagation

```merit
fn increment(value: i32) -> IntResult {
    let checked: i32 = try validate(value);
    return Ok(checked_add(checked, 1));
}
```

`try` is currently restricted to typed local bindings. Its input and containing function must use Result-shaped nominal enums with variants ordered `Ok`, `Err`. The `Err` payload types must agree. An error returns immediately through the function epilogue.

## Filesystem errors

Filesystem operations retain their lexical `file_read` and `file_write` capability requirements and return built-in nominal results:

```merit
enum FsError { FsNotFound, FsPermissionDenied, FsIoError }
enum FileReadResult { ReadOk(Buffer), ReadErr(FsError) }
enum FileWriteResult { WriteOk(i64), WriteErr(FsError) }
```

`file_read(allocator, path)` and `file_write(path, buffer)` never expose host exceptions or terminate native execution for ordinary OS failures. Both execution paths map missing paths, permission failures, and other I/O errors to the same `FsError` variants. Allocation failure remains a separate fatal allocation hazard.

## Visibility

Project declarations are private by default. Prefix exported declarations with `pub`:

```merit
pub enum IntResult { Ok(i32), Err(MathError) }
pub fn validate(value: i32) -> IntResult { ... }
```

A consuming module must both import the owner module and use only symbols exported by it.
