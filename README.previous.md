# Merit — Epoch II Application Language

Merit is a native compiled language experiment centered on deterministic semantics, exact numerics, ownership, explicit allocation, contracts, stable layouts, capability-specific hazardous operations, and C interoperability.

Epoch II is the first closed application-language epoch. It supports multi-module projects, payload enums and exhaustive matching, typed Result-style propagation, UTF-8 string views, owned byte buffers, explicit allocators, deterministic cleanup, CFG-shaped MIR, interpretation, C11 generation, native compilation, and differential verification.

## Install

```bash
python -m pip install -e .
```

A C11 compiler such as Clang or GCC is required for native builds.

## Run the Epoch II acceptance application

```bash
merit-project graph examples/projects/text_pipeline
merit-project check examples/projects/text_pipeline
merit-project verify examples/projects/text_pipeline
merit-project run examples/projects/text_pipeline
```

Expected output:

```text
Merit Epoch II
abc!
4
327
```

## Core example

```merit
module text_main
import text;

capability allocate;

fn main() -> i32 {
    print("Merit Epoch II");
    with capability allocate {
        let allocator: Allocator = system_allocator();
        var data: Buffer = buffer_from_string(allocator, "abc");
        buffer_push(data, 33);
        print(data);
        print(buffer_len(data));
        print(checksum(data));
        drop(data);
    }
    return 0;
}
```

## Commands

Single-file compiler:

```bash
merit check program.mrt
merit interpret program.mrt
merit build program.mrt -o program
merit exec program.mrt
merit verify program.mrt
merit hir program.mrt
merit mir program.mrt
```

Project compiler:

```bash
merit-project graph PATH
merit-project check PATH
merit-project build PATH
merit-project run PATH
merit-project verify PATH
```

## Status

The test suite contains 41 passing tests. The implementation remains Python-hosted and uses generated C11 as its native backend. See `EPOCH-II.md` for the completed scope and `ROADMAP.md` for Epoch III.

## Epoch III systems core

The first Epoch III checkpoint adds non-owning byte slices and an allocator-backed owned integer vector.

```merit
let payload: ByteSlice = buffer_slice(packet, 2, 3);
var values: I64Vec = i64vec_new(allocator, 2);
i64vec_push(values, checksum(payload));
drop(values);
```

Run the binary packet acceptance project:

```bash
merit-project verify examples/projects/binary_packet
merit-project run examples/projects/binary_packet
```

See `EPOCH-III.md` for the completed scope and remaining epoch work.

## Epoch III generic checkpoint

Merit now supports explicitly instantiated generic structs, enums, and functions:

```merit
struct Pair<T, U> {
    first: T;
    second: U;
}

enum Option<T> {
    Some(T),
    None
}

fn maximum<T: Ord>(left: T, right: T) -> T {
    if (left >= right) { return left; } else { return right; }
}
```

Concrete uses are monomorphized before normal semantic checking:

```merit
let pair: Pair<i64, i32> = Pair<i64, i32> { first: 7, second: 3 };
let value: Option<i64> = Option<i64>::Some(42);
let best: i64 = maximum<i64>(7, 42);
```

Verify the included acceptance project:

```bash
merit-project verify examples/projects/generic_result
```
