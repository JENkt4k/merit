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

## 0.1 proof obligations

- Exact scaled-decimal arithmetic
- Bounded values
- Capability auditing
- Typed interpreter
- Native compilation
- Compile-time rejection of implicit precision loss
