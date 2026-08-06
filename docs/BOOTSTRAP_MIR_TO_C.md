# Bootstrap MIR-to-C Core

This document defines the first executable backend slice from `bootstrap-mir-v1` to deterministic C.

## Purpose

The backend consumes ordered MIR directly. It does not rebuild Merit expression trees, infer evaluation order, or assign numeric semantics. Every emitted statement follows MIR instruction order and every transfer follows an explicit terminator.

## Supported types

- `i64` → `int64_t`
- `bool` → `bool`
- `unit` → `void` return type

Generic and aggregate types fail closed in this slice.

## Supported instructions

- scalar constants
- copy, move, and borrow as explicit scalar assignments
- supported binary operators with `exact`, `checked`, or `floating` policy
- exact and checked scalar conversions
- contract checks
- capability checks
- scalar no-op drop/deallocate markers

Calls, constructors, fields, allocation, aggregates, wrapping arithmetic, saturating arithmetic, rounded conversions, truncating conversions, and reinterpretation are deferred and rejected.

## Supported terminators

- return
- jump
- branch
- switch
- unreachable

Basic blocks are emitted as deterministic labels. Branches and switches use explicit `goto` transfers. C fallthrough is never used to encode Merit control flow.

## Determinism

- functions are emitted in MIR order
- locals are emitted in MIR order
- blocks are emitted in MIR order
- instructions are emitted in MIR order
- switch cases are emitted in MIR case order
- identifiers are sanitized deterministically
- generated files contain no timestamps or host-specific paths

## Native verification

Tests compile generated C using the system C compiler with:

```text
-std=c11 -Wall -Wextra -Werror
```

The resulting executables validate arithmetic, if/else selection, loop back edges, and switch dispatch.

## Next slices

1. checked overflow helpers that preserve Merit numeric policies
2. resolved calls and stable exported function signatures
3. aggregates, fields, constructors, and stable layouts
4. explicit allocation/deallocation and cleanup edges
5. complete HIR → MIR → C vertical acceptance programs
