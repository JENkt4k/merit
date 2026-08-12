# Language Strategy: What Merit Should Preserve and Avoid

Merit is not based on the assumption that existing languages failed. Many languages contain excellent ideas and have survived because those ideas remain useful. The design goal is to distinguish enduring concepts from accidental complexity, ecosystem lock-in, or implementation mechanisms that should remain evolvable.

This document summarizes lessons Merit should draw from several major language families. It is not a claim that Merit is already superior to mature production implementations; performance, productivity, and migration claims must be measured.

## COBOL

### Enduring strengths

- business-oriented fixed-point decimal arithmetic;
- explicit data descriptions and record structure;
- predictable batch processing;
- exceptional backwards compatibility;
- direct expression of business data constraints.

### Long-term weaknesses to avoid

- installed estates tightly coupled to historical storage and runtime assumptions;
- architecture and data representation becoming difficult to separate;
- specialized tooling and shrinking expertise pools;
- large monolithic programs and shared copybooks that make evolution risky;
- limited expression of contemporary ownership, concurrency, generic, and capability constraints.

### Merit lesson

Preserve exact business semantics while isolating historical storage representations behind explicit compatibility boundaries.

## C

### Enduring strengths

- small conceptual core;
- transparent native execution model;
- ubiquitous ABI and systems interoperability;
- predictable compilation and deployment;
- extraordinary implementation longevity.

### Long-term weaknesses to avoid

- memory and lifetime safety largely depend on programmer discipline and tooling outside the core language;
- integer overflow, aliasing, and undefined-behavior hazards can be subtle;
- abstractions for generic, concurrent, and resource-safe programming are comparatively weak.

### Merit lesson

Keep C's interoperability and understandable machine model while making important safety and numeric guarantees structural.

## C++

### Enduring strengths

- deterministic resource management through RAII;
- powerful zero-cost abstractions;
- templates and generic programming;
- broad access to low-level optimization and hardware features;
- major investments in backwards compatibility.

### Long-term weaknesses to avoid

- enormous accumulated language surface;
- overlapping generations of idioms and ownership models;
- difficult compile-time behavior in large template-heavy systems;
- complexity that can make it hard to identify the one preferred safe way to express an operation.

### Merit lesson

Preserve deterministic resource management and native abstraction without indefinitely accumulating competing mechanisms for the same semantic job.

## Java

### Enduring strengths

- highly successful virtual-machine abstraction;
- strong portability story;
- mature garbage collection and runtime tooling;
- large ecosystem and productive application model;
- substantial source and bytecode compatibility effort over decades.

### Long-term weaknesses to avoid

- application longevity can depend on the complete stack: JDK, application server, framework, libraries, build tooling, deployment model, and database integrations;
- old applications can become trapped by framework and dependency combinations even when the language remains supported;
- critical numeric and domain constraints such as precision, scale, rounding, and valid ranges are often reconstructed through libraries and conventions rather than the core type system;
- runtime abstraction can make low-level layout, deterministic resource behavior, and native interoperability less direct.

### Merit lesson

Language compatibility is necessary but insufficient. Minimize semantic dependence on framework generations and keep important domain invariants visible in the language.

## C# / .NET

### Enduring strengths

- productive modern type system;
- useful value types and built-in `decimal` support;
- mature tooling and runtime;
- strong async and application-development ecosystem;
- practical native interoperability.

### Long-term weaknesses to avoid

- applications can still inherit framework/runtime/version coupling;
- managed runtime assumptions may not fit every systems or deterministic-resource workload;
- correctness policies remain distributed across language features, libraries, attributes, frameworks, and storage schemas.

### Merit lesson

Built-in decimal support is valuable, but a systems language for long-lived financial and numerical work should integrate numeric domains with contracts, bounded values, ownership, stable layouts, and explicit resource semantics.

## Rust

### Enduring strengths

- memory safety without mandatory garbage collection;
- ownership and borrowing made central to language design;
- traits and composition-oriented abstraction;
- expressive enums and pattern matching;
- strong concurrency safety goals;
- deliberate compatibility through editions.

### Risks Merit should avoid

Rust demonstrates the value of moving correctness reasoning into the compiler, but also how much responsibility sophisticated static analysis places on compiler architecture and developer feedback. Complex lifetime, trait, generic, and monomorphization work can increase compile-time cost, and a language should avoid making one generation of proof machinery inseparable from its permanent semantic contract.

This is not an argument that Rust is frozen or inherently unsuitable for SIMD, ABI work, or systems optimization. Rather, Merit should learn from the tradeoff: specify durable ownership and safety guarantees while leaving room to replace the algorithms used to prove them, and make incremental semantic caching a first-class architectural goal.

### Merit lesson

Adopt the guarantee, not necessarily every mechanism. Memory safety should be permanent; today's exact analysis strategy should not have to be.

## Ada / SPARK

### Enduring strengths

- range-constrained types;
- contracts and formal verification;
- strong emphasis on correctness and explicitness;
- mature safety-critical engineering model.

### Weaknesses to avoid

- safety-oriented languages can lose adoption if ergonomics, ecosystem integration, or ordinary systems-development workflows become too specialized or expensive.

### Merit lesson

Bring contracts, bounded domains, and verification closer to mainstream systems ergonomics and native interoperability.

## Fortran

### Enduring strengths

- numerical computing as a primary language concern;
- array semantics and optimization opportunities;
- decades of compatibility with high-performance scientific software.

### Weaknesses to avoid

- historical language layers and specialized scientific conventions can make modernization uneven;
- resource safety and modern systems abstractions were not central to the original model.

### Merit lesson

Numerical semantics, arrays, vectorization, and optimization should be language-level concerns rather than generic-library afterthoughts.

## Functional and ML-family languages

### Enduring strengths

- algebraic data types;
- pattern matching;
- explicit treatment of side effects in some systems;
- composition and immutability;
- powerful type inference and formal foundations.

### Weaknesses to avoid

- very abstract type machinery can become difficult to diagnose or integrate with low-level layout and resource constraints;
- some implementations prioritize managed/runtime models over direct systems interoperability.

### Merit lesson

Use algebraic types, exhaustive matching, traits/effects/capabilities, and composition where they clarify semantics, but retain explicit resource and machine boundaries.

## What appears mature

The programming-language field has explored many fundamental paradigms deeply:

- procedural programming;
- functional programming;
- object-oriented programming;
- generic programming;
- traits, interfaces, protocols, and type classes;
- algebraic data types and pattern matching;
- ownership and deterministic resource management;
- actors/message passing;
- contracts and refinement/range constraints;
- data-parallel programming.

This does not mean language research is finished. It suggests that future improvement may increasingly come from combining mature concepts coherently and making more correctness properties mechanically enforceable without sacrificing comprehensibility, performance, interoperability, or incremental build speed.

## Merit strategy

Merit should resist replacement-for-replacement's-sake. A feature should enter the language because it expresses an enduring concept better, not because another language currently makes that feature fashionable.

The intended synthesis is approximately:

| Goal | Merit direction |
| --- | --- |
| Native performance | C/C++/Fortran-style direct compilation and optimization |
| Exact business numerics | COBOL/Ada-inspired structural numeric domains |
| Numerical computing | Fortran-style language awareness of numeric/array semantics |
| Resource safety | C++ deterministic management plus ownership-based verification |
| Memory safety | compiler-enforced lifetime and ownership guarantees |
| Behavioral abstraction | traits and composition rather than inheritance-heavy class models |
| Correctness | contracts, bounds, exhaustive types, checked arithmetic |
| Hazard control | explicit capabilities/effects |
| Migration | stable layouts, C interoperability, deterministic legacy adapters |
| Longevity | stable semantics with replaceable proof/compiler machinery |

Merit should be judged against these goals by evidence: compiler behavior, differential tests, compatibility fixtures, compile-time measurements, native performance benchmarks, and real migrations. The philosophy defines what to optimize for; measurement determines whether the implementation succeeds.
