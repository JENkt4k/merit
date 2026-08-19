# Traits and generics

Traits describe behavior that types can implement. Generic functions may require trait bounds, allowing code to depend on a small behavioral contract instead of a concrete type.

## Declaring a trait

```merit
trait Summarized {
    fn score(value: Self) -> i32;
}
```

`Self` means the implementing type.

## Implementing a trait

```merit
stable("v1") struct Point {
    x: i32;
}

impl Summarized for Point {
    fn score(value: Point) -> i32 {
        return value.x;
    }
}
```

The implementation must satisfy the trait method signature for the concrete type.

## Using trait bounds

```merit
fn summarize<T: Summarized>(value: T) -> i32 {
    return score(value);
}

fn main() -> i32 {
    let p: Point = Point { x: 17 };
    let total: i32 = summarize<Point>(p);
    print(total);
    return 0;
}
```

The current alpha uses explicit generic instantiation (`summarize<Point>(...)`). The compiler monomorphizes established generic declarations into concrete instances before the normal semantic/ownership/MIR pipeline.

## Coherence

Trait implementations are coherent: Merit does not permit ambiguous competing implementations for the same trait/type pairing. A call with a satisfied bound therefore resolves to one implementation rather than depending on import order or runtime discovery.

## Traits are not classes

Traits express required behavior. They do not imply inheritance, hidden object identity, mandatory heap allocation, or a class hierarchy. State lives in concrete values; a trait bound says which operations are available to generic code.

This makes traits useful for reusable algorithms without forcing dependency-injection containers or inheritance trees into the language model.

## Ownership still applies

Trait methods and generic functions use the same parameter modes as ordinary functions. A `value` parameter may consume an owned argument; `borrow` and `borrow_mut` preserve ownership while granting temporary access.

When writing generic APIs, choose the narrowest ownership mode that matches the operation:

- use `borrow` to inspect,
- use `borrow_mut` to mutate without taking ownership,
- use value mode when the operation truly consumes or transfers the value.

## Current limits

Trait objects/dynamic dispatch and specialization are outside the current alpha. The established surface is coherent static traits plus explicit generics/monomorphization. Those omissions are deliberate rather than partially emulated.

See the executable example at `examples/projects/trait_bounds` for the canonical current syntax.
