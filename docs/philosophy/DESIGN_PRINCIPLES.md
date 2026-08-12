# Merit Design Principles

This document turns Merit's philosophy into engineering review criteria. It is intended to constrain language and compiler evolution, not merely describe current implementation choices.

## 1. Preserve meaning before syntax

Language evolution should prioritize stable program meaning over fashionable syntax. New syntax is justified when it clarifies semantics, removes ambiguity, or exposes an important guarantee.

## 2. Make enduring invariants structural

Properties central to correctness should be expressed by the language when practical rather than reconstructed through libraries, annotations, framework configuration, or developer convention.

Examples include exact numeric domains, bounded values, ownership state, contracts, capabilities, and stable external layouts.

## 3. Specify guarantees, not unnecessary proof algorithms

The language should define properties a valid program receives. Compiler internals should remain free to improve as long as those properties remain true.

A safety guarantee belongs in the language contract. A particular borrow checker, optimizer, IR, or theorem-proving strategy normally does not.

## 4. Prefer composition over inheritance

Data representation, behavioral contracts, implementation, and reuse are separate concerns. Merit prefers records/structs, traits, explicit implementations, and composition over deep class inheritance hierarchies.

## 5. Exactness must be intentional

Financial, scientific, and systems software should not depend on accidental numeric behavior. Precision, scale, rounding, overflow, narrowing, and cross-domain conversion should be visible and deterministic where they affect correctness.

## 6. Unsafe or hazardous operations must be visible

Operations with external or safety-sensitive consequences should cross explicit boundaries. Capability-specific operations, foreign interfaces, allocation, filesystem access, and other hazards should be inspectable rather than hidden behind ordinary-looking calls.

## 7. Compatibility belongs at boundaries

Legacy encodings, foreign ABIs, historical wire formats, and platform-specific representations should be supported explicitly without becoming implicit semantics of ordinary Merit values.

Canonical internal representations should remain independent of compatibility adapters whenever possible.

## 8. Determinism is a feature

Equivalent accepted Merit programs should have predictable language-defined behavior independent of whether they execute through the reference interpreter or generated native code. Platform variability should be explicit where unavoidable.

## 9. Strong analysis must remain incrementally affordable

Compile-time safety should not imply repeatedly analyzing unchanged code. Semantic dependencies, proof results, verified IR, and object artifacts should be cacheable when their defining inputs have not changed.

Compiler sophistication should improve developer feedback, not create avoidable full-build costs.

## 10. Interoperability is part of migration safety

A new systems language cannot demand flag-day rewrites. Merit should maintain practical C and stable-layout boundaries and provide deterministic adapters for important legacy systems so components can be replaced incrementally.

## 11. Unsupported behavior should fail closed

Migration and low-level tooling must reject ambiguous or unsupported constructs rather than silently infer plausible semantics. A deterministic diagnostic is safer than a successful but incorrect translation.

## 12. Backwards compatibility is a design responsibility

Once a behavior is part of Merit's stable language contract, changing its meaning should have an extremely high bar. Language editions or compatibility modes may alter accepted syntax or add features, but old source should not silently acquire different semantics.

## 13. Performance and safety are co-equal engineering requirements

Safety mechanisms should be designed with native execution, predictable resource behavior, vectorization, interoperability, and optimization in mind. Merit should not treat performance as an afterthought layered onto correctness, nor correctness as an optional layer above performance.

## 14. The compiler should explain its decisions

Ownership errors, contract failures, capability requirements, layout decisions, numeric-domain conflicts, and migration diagnostics should expose enough structured information for humans and tools to understand why a program was accepted or rejected.

This becomes increasingly important for AI-assisted development: machine-generated code should be constrained by explicit semantics and receive precise feedback rather than depend on hidden convention.

## 15. Every abstraction must justify its longevity cost

A feature that is convenient today can become permanent compatibility debt. Before adding a new abstraction, Merit should ask whether it represents an enduring computational concept, whether it composes with existing semantics, and whether the same goal can be achieved without freezing an implementation detail into the language.

## Review heuristic

For a substantial language proposal, reviewers should be able to answer:

1. What enduring problem does this solve?
2. Which semantics become stronger or clearer?
3. Which implementation choices remain replaceable?
4. What are the compatibility consequences?
5. What is the performance model?
6. Can unchanged code avoid repeated analysis?
7. Does the feature interact cleanly with exact numerics, ownership, contracts, capabilities, traits, stable layouts, and C interoperability?
8. How would we explain this feature to a maintainer decades from now?

If those answers are unclear, the proposal is not yet ready to become part of Merit's permanent language surface.
