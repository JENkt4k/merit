# COBOL Modernization with Merit

Merit's COBOL work is intended to demonstrate a migration architecture, not a claim that all COBOL estates can already be translated automatically.

The core idea is:

> **Preserve enduring business semantics. Isolate historical physical representation. Replace systems incrementally.**

## Why COBOL remains difficult to replace

COBOL survived because many of its original business-computing requirements remain valid:

- exact decimal arithmetic;
- explicit records and data descriptions;
- deterministic batch behavior;
- bounded business fields;
- decades of backward compatibility.

The modernization problem is the accumulated software estate around those strengths:

- mainframe and runtime dependence;
- shared copybooks and tightly coupled schemas;
- batch-oriented architectures that are hard to decompose;
- historical encodings such as EBCDIC, zoned decimal, and COMP-3;
- large bodies of business logic whose behavior may be poorly documented outside the source;
- integration assumptions tied to old storage, transaction, and deployment models;
- shrinking availability of engineers deeply familiar with specific legacy estates.

A rewrite therefore has two separate jobs:

1. preserve the business semantics that still matter;
2. remove implementation constraints that no longer need to define the future system.

Those jobs should not be confused.

## The semantic reconstruction problem

General-purpose replacement languages can implement financially correct software. The risk is that guarantees previously expressed directly in data declarations become distributed across libraries, validation code, schemas, framework configuration, serializers, and developer convention.

For example, a general-purpose declaration such as a `BigDecimal` field does not by itself state the entire business contract: permitted precision, required scale, rounding policy, valid range, conversion rules, and overflow behavior may live elsewhere.

Merit aims to pull durable invariants back into the language surface:

```merit
decimal USD(18, 2, half_even);
bounded AccountNumber(u64, 1, 999999999999);
```

That does not eliminate the need for database constraints, persistence transactions, or integration tests. It reduces the number of independent mechanisms required merely to describe the computational domain correctly.

## Migration boundary

Merit deliberately does not treat COBOL storage formats as ordinary native Merit semantics.

```text
existing COBOL / copybook bytes
        |
        v
explicit compatibility adapter
(EBCDIC, zoned, COMP-3, binary, layout)
        |
        v
versioned canonical Merit record
        |
        v
exact / bounded Merit domain model
        |
        v
verified business computation
        |
        +--> modern storage/services/native ABI
        |
        v
optional adapter back to legacy representation
```

COMP-3 is a compatibility representation. Exact fixed-scale decimal arithmetic is the enduring semantic concept.

That separation allows the old and new system to coexist during a strangler migration rather than requiring a flag-day replacement.

## Current repository example

The repository currently contains two complementary pieces.

### `cobol_finance_modernization`

The financial example demonstrates:

- exact `USD` arithmetic;
- bounded account and sequence domains;
- stable canonical records;
- checked arithmetic;
- executable contracts;
- typed transaction outcomes;
- duplicate/out-of-order protection;
- explicit legacy bridge functions;
- interpreter/native differential verification.

It intentionally leaves durable atomic commit to an appropriate storage/journal layer. Language-level numeric correctness does not replace transactional persistence.

### `merit-copybook`

The copybook toolkit demonstrates the compatibility boundary:

- constrained deterministic copybook parsing;
- byte offsets and record manifests;
- CP037 EBCDIC text;
- zoned decimal;
- COMP-3 / packed decimal;
- canonical binary fields;
- fixed `OCCURS n TIMES`;
- exact record encode/decode;
- stable canonical Merit generation;
- C raw-record interoperability metadata;
- byte-for-byte golden-vector verification;
- fail-closed handling of unsupported or ambiguous constructs.

Together they demonstrate the intended path from legacy bytes to canonical Merit computation.

## Why not just translate syntax?

A syntax translator can preserve the appearance of the original program while weakening its invariants. A safer modernization system should compare observable behavior.

A future migration workflow should support something like:

```text
same production-derived or approved test corpus
             |
       +-----+-----+
       v           v
    COBOL         Merit
       |           |
       +-----+-----+
             v
      semantic comparator
             |
             +-- exact values
             +-- record bytes
             +-- status/error outcomes
             +-- ordering
             +-- overflow behavior
             +-- externally visible side effects
```

For an approved migration corpus `X`, the target is behavioral equivalence for the modeled contract:

```text
for every x in X:
    observable_behavior(COBOL, x) == observable_behavior(Merit, x)
```

That does not prove equivalence for all possible inputs unless stronger formal methods are applied. It does provide a disciplined differential migration path and can be extended with formal properties where the domain justifies them.

## Why Merit may be a better target than a conventional rewrite

The intended advantages are architectural rather than assumed benchmark results:

| Concern | Conventional general-purpose rewrite risk | Merit direction |
| --- | --- | --- |
| Financial exactness | library/convention dependent | first-class decimal domains |
| Range constraints | validation scattered across layers | bounded types/contracts |
| Overflow | primitive/library-dependent behavior | explicit checked semantics |
| Legacy records | ad hoc DTO/mapping code | generated deterministic boundary |
| Memory/resource behavior | runtime or discipline dependent | ownership/resource guarantees |
| Business failure states | exceptions/status conventions | typed exhaustive outcomes |
| Interoperability | framework-specific bridge | stable layouts and C boundary |
| Migration verification | project-specific testing | differential/golden strategy |
| Unsupported legacy constructs | translator may guess | fail closed |

Claims about superior runtime performance, development cost, defect rates, or migration effort must eventually be supported by measured benchmarks and real conversion studies. The language architecture is designed to make those outcomes plausible; it does not make them automatic.

## Avoiding a second legacy trap

Replacing COBOL with a contemporary language is not enough if the replacement becomes stranded on today's framework, VM, proof algorithm, or deployment model.

Merit's semantic-longevity doctrine therefore matters directly to COBOL modernization:

- exact numeric meaning should not depend on one library version;
- stable records should not depend on one runtime object model;
- ownership guarantees should not require today's exact checker implementation forever;
- compiler optimizations and hardware mappings should be replaceable;
- legacy compatibility should remain isolated at boundaries;
- unchanged verified components should be reusable through incremental analysis and caching.

The goal is not simply to move a 40-year-old system into a new language. It is to reduce the probability that the new system requires another wholesale language migration decades later.

## Scope of the current proof

The present examples are deliberately small. They are sufficient to demonstrate the architecture but not to claim production COBOL replacement readiness.

A mature migration system would still need broader copybook coverage, dialect/platform profiles, database and transaction adapters, batch/file workflows, richer control-flow translation, source-to-source analysis, data-flow reconstruction, operational migration tooling, and substantially larger differential corpora.

That future work should preserve the same boundary:

> **Legacy representation may expand at the edge; Merit's enduring semantic core should remain clean.**
