# Bootstrap Checked Arithmetic and Calls

This document describes the second executable `bootstrap-mir-v1` to C backend
slice. It extends deterministic scalar C emission with portable checked `i64`
arithmetic and validated calls between MIR functions.

## Backend path

```text
validated bootstrap-mir-v1
→ deterministic helper and prototype selection
→ ordered C statements and explicit control flow
→ C11 compiler
→ native executable
```

The backend still consumes validated MIR. It does not reconstruct Merit
expressions, infer evaluation order, invent conversions, or infer an aggregate
ABI.

## Checked `i64` operations

The `checked` numeric policy is implemented for:

- addition
- subtraction
- multiplication
- division
- remainder

Helpers test the operation before executing any C expression that could trigger
signed overflow, division by zero, or the `INT64_MIN / -1` exceptional case.
Failure calls a deterministic numeric-failure hook and aborts. The helper is
emitted only when a MIR instruction requires that operation.

The helpers are written in portable C11 using `INT64_MIN`, `INT64_MAX`, and
precondition checks. This slice does not depend on GCC or Clang overflow
builtins.

The `exact` policy remains direct scalar C emission in this bootstrap subset.
Broader exact-integer semantics and arbitrary-width lowering remain future work.

## Function calls

The module emitter now:

1. validates that distinct Merit function names do not sanitize to the same C
   identifier;
2. emits deterministic forward prototypes for all MIR functions;
3. resolves every call symbol against the MIR module;
4. checks the callee return type;
5. requires a result local for value-returning calls;
6. rejects a result local for `unit` calls.

The current `bootstrap-mir-v1` function contract does not identify parameter
locals or carry a stable parameter list. Therefore this backend slice supports
only no-argument calls. Calls with operands fail explicitly until the MIR
function-signature contract is extended.

## Determinism

- runtime helpers are selected solely from MIR instruction kinds and policies;
- helpers are emitted in a fixed order;
- function prototypes follow MIR module order;
- function definitions follow MIR module order;
- calls use validated sanitized identifiers;
- no timestamps, paths, compiler versions, or allocation addresses appear in
  generated C.

## Native verification

The test suite compiles generated C as C11 with:

```text
-Wall -Wextra -Werror
```

It executes successful checked operations, multi-function calls, unit calls,
and `INT64_MIN` literal handling. It also verifies that overflow, invalid
division, and invalid remainder terminate instead of wrapping or invoking
undefined C behavior.

## Deferred work

- parameter and argument ABI contracts
- exported/public C symbol policy
- aggregate layouts and by-value/by-reference rules
- decimal checked helpers
- typed error returns instead of the bootstrap abort hook
- allocation and cleanup edges
- cross-module symbol linkage
