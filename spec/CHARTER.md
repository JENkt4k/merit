# Merit 0.1 Semantic Charter

Merit is a small native compiled language for deterministic, numerically exact, resource-safe components.

## Constitutional rules

1. Optimization may change performance, never program meaning.
2. Decimal narrowing, rounding, overflow, allocation, foreign calls, and hazardous operations are never implicit.
3. Hazardous operations are classified by capability rather than hidden behind a generic unsafe category.
4. Types crossing binary boundaries must select a documented stable or foreign layout.
5. Resource acquisition has deterministic release; no mandatory tracing collector exists.
6. Debug and release builds share bounds, overflow, initialization, contract, and arithmetic semantics.
7. Post-1.0 source semantics and ABI specifications evolve only through explicit versioning.
8. Expressions evaluate exactly once from left to right, independent of the native backend's operand-order rules.

## 0.1 proof obligations

- Exact scaled-decimal arithmetic
- Bounded values
- Capability auditing
- Typed interpreter
- Native compilation
- Compile-time rejection of implicit precision loss

## Contract observations

- Preconditions and postconditions may call functions proven read-only by conservative body inspection.
- Calls with mutable-borrow parameters, declared effects, or capability-gated hazards are rejected in contracts.
- `old(expression)` is postcondition-only and currently requires a Copy result. Owned snapshots remain unavailable until their allocator, cloning, and destruction policy is explicit.
