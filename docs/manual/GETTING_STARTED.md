# Getting started

A Merit source file begins with a module declaration and then declares types, capabilities, traits, functions, and other module items.

```merit
module hello

fn main() -> i32 {
    print(42);
    return 0;
}
```

For a single file, the reference compiler provides commands such as:

```bash
merit check program.mrt
merit verify program.mrt
merit layout program.mrt
merit audit program.mrt
```

Projects use `Merit.toml` plus source modules and the `merit-project` commands:

```bash
merit-project check PATH
merit-project verify PATH
merit-project run PATH
merit-project layout PATH
merit-project audit PATH
```

## Bindings

`let` introduces an immutable binding and `var` introduces a mutable binding.

```merit
let answer: i32 = 42;
var counter: i32 = 0;
counter = counter + 1;
```

Whether a value can be copied is determined by its type. Scalar values are generally copyable; owned resource-bearing values are moved instead. See [Ownership and borrowing](OWNERSHIP.md).

## Functions

Functions declare parameter and return types explicitly.

```merit
fn add(left: i32, right: i32) -> i32 {
    return left + right;
}
```

Generic functions use explicit type parameters and are explicitly instantiated at call sites in the current alpha:

```merit
fn identity<T>(value: T) -> T {
    return value;
}

let result: i32 = identity<i32>(7);
```

Trait bounds constrain generic parameters:

```merit
fn summarize<T: Summarized>(value: T) -> i32 {
    return score(value);
}
```

## Structures and stable layout

Structs define named fields. `stable("...")` gives a layout/version identity for ABI-sensitive types.

```merit
stable("point-v1") struct Point {
    x: i32;
    y: i32;
}

let p: Point = Point { x: 3, y: 4 };
```

Stable layout is a contract: change it deliberately rather than assuming the compiler may silently reorder ABI-visible data.

## Control flow

The established language includes structured `if`, `while`, `match`, and typed propagation constructs. Evaluation order is defined: sibling operands and function arguments evaluate exactly once, left to right.

## Exactness and safety

Merit includes exact fixed-scale decimals and bounded/checked integer facilities because numeric meaning is intended to be explicit. It also uses contracts, capabilities, ownership, and deterministic destruction to make failure and authority visible in source.

## Reference compiler versus replacement compiler

During `v0.1.0-alpha.2`, the Python-hosted compiler remains the semantic oracle while the Merit-native replacement compiler is built out. This is an implementation transition, not a language fork. Programs should target the documented language semantics, not implementation quirks of either compiler path.
