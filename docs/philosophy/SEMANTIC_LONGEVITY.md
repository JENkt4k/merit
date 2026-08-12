# Semantic Longevity

Merit is designed around a simple long-term rule:

> **Freeze meaning. Evolve implementation.**

Programming languages routinely enter a cycle of adoption, maturity, ecosystem growth, compatibility pressure, declining expertise, and eventual migration. That cycle is expensive because the work being migrated often still expresses valid business or systems semantics. The problem is frequently not that the old program became conceptually wrong, but that its implementation environment became difficult to evolve.

Merit's objective is not to become another temporary replacement language. It is to make enduring program meaning stable while allowing compiler algorithms, proof machinery, optimizers, code generators, runtimes, hardware targets, and development tooling to improve beneath it.

## Stable semantic kernel

Concepts that describe enduring computation should remain small, explicit, and highly stable. Examples include:

- integers and exact decimals;
- floating-point values with explicit semantics;
- arrays, records, enums, functions, and modules;
- traits and explicit implementations;
- bounded values and explicit conversions;
- contracts;
- stable external layouts and interoperability boundaries.

A declaration such as:

```merit
decimal USD(18, 2, half_even);
```

should retain the same meaning across future Merit implementations. A later compiler may use different lowering strategies or future hardware instructions, but precision, scale, rounding, overflow, and conversion semantics must not silently drift.

## Stable guarantees, replaceable proof machinery

Merit should specify guarantees rather than unnecessarily freezing today's algorithms for proving them.

Examples of stable guarantees include:

- memory safety;
- resource safety;
- deterministic destruction where promised;
- defined overflow behavior;
- capability restrictions;
- contract enforcement;
- race-prevention rules;
- exact numeric semantics.

The machinery used to establish those guarantees may evolve:

- ownership and borrow analysis;
- escape analysis;
- alias analysis;
- effect analysis;
- range analysis;
- concurrency analysis;
- formal verification techniques;
- optimizer and code-generation strategies.

For example, "a reference cannot outlive the storage it references" is an enduring semantic guarantee. A particular borrow-checking implementation is not.

## Layering for longevity

Merit should preserve a strong separation between four layers:

1. **Semantic kernel** — what a program means.
2. **Behavioral guarantees** — what the compiler and runtime must ensure.
3. **Proof and analysis machinery** — how those guarantees are established.
4. **Platform implementation** — how the verified program maps to x86, ARM, RISC-V, SIMD, GPUs, WASM, or future architectures.

The lower layers should be able to evolve without invalidating the upper layers.

## Compatibility is not semantics

Historical storage and ABI formats matter during migration, but they should not automatically become permanent language concepts.

For example, COBOL COMP-3 is an important compatibility representation. Exact fixed-scale decimal arithmetic is the enduring semantic concept. Merit therefore keeps COMP-3 decoding at an explicit migration boundary and represents the resulting value using canonical Merit numeric types.

This distinction prevents old implementation constraints from contaminating new program meaning while still supporting incremental migration.

## Incremental verification

Strong static guarantees do not require re-proving an entire application on every edit. Merit should make semantic work cacheable by content and dependency identity.

Conceptually:

```text
source
  -> parsed representation
  -> typed representation
  -> ownership/effect proofs
  -> verified IR
  -> optimized IR
  -> object code
```

If a module and the semantic dependencies that affect it have not changed, previously established analysis results should be reusable. Merit's existing content-addressed object caching is an initial step toward this broader model; future per-module and semantic-proof caching should preserve the same principle.

## Language evolution without language churn

Many major programming paradigms are already mature: procedural, functional, generic, object-oriented, data-parallel, message-passing, algebraic data types, traits, contracts, and ownership-based safety.

Future progress is likely to come increasingly from moving properties that developers previously maintained through convention into machine-verifiable semantics, while keeping those semantics comprehensible and implementation-independent.

Traits illustrate this evolution. Traditional class hierarchies often bundle data representation, identity, implementation inheritance, polymorphism, and reuse. Merit prefers separating those concerns: records describe data, traits describe behavior, implementations establish relationships, and composition provides reuse.

## The long-term test

A future Merit feature should be challenged with questions such as:

- Is this an enduring semantic concept or today's implementation mechanism?
- Can the guarantee remain stable if compiler research changes substantially?
- Does this feature unnecessarily couple source meaning to one hardware generation?
- Does it preserve deterministic and inspectable behavior?
- Can unchanged code retain previously established proofs?
- Does the feature reduce long-term semantic ambiguity rather than move it into conventions or frameworks?

Merit's success should not be measured only by whether it can replace an older language today. A stronger test is whether a program written in Merit today can remain meaningful decades from now while its compiler is completely replaced underneath it.
