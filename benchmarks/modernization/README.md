# Merit Modernization Benchmark

This benchmark is an evidence harness for the COBOL-modernization thesis. It is deliberately language-neutral at the corpus boundary: implementations must consume the same ordered transaction corpus and produce the same canonical result stream before performance comparisons are meaningful.

## Goals

1. Correctness before speed. Every implementation must match the canonical results exactly.
2. Separate semantic migration from physical legacy encoding. Copybook/EBCDIC/COMP-3 compatibility is tested independently from financial behavior.
3. Measure migration-relevant properties rather than a synthetic arithmetic loop.
4. Keep results reproducible and machine-readable so COBOL, Java, C#, Rust, C++, and Merit implementations can be added without changing the corpus.

## Workload v1

`transaction_corpus.json` models ordered account postings with:

- exact cents, represented in the corpus as signed integer minor units;
- bounded account identifiers and monotonically increasing sequence numbers;
- successful transfers;
- insufficient-funds rejection;
- duplicate/out-of-order rejection;
- same-account rejection;
- invalid non-positive amount rejection;
- destination-overflow rejection;
- state preservation after rejected transactions.

The corpus avoids binary floating-point and host-language decimal conventions. Each implementation chooses its native representation, but must reproduce the canonical observable behavior.

## Runner contract

`run_reference.py` validates the corpus and emits one JSON object containing:

- corpus identity and SHA-256;
- transaction count and committed/rejected counts;
- final account balances and sequences;
- ordered outcome digest;
- elapsed time and transactions/second as informational local measurements.

The digest excludes timing so identical semantics produce identical evidence across machines.

Run:

```bash
python benchmarks/modernization/run_reference.py
python benchmarks/modernization/run_reference.py --json
```

## Comparison policy

A future implementation is benchmark-eligible only after its canonical outcome digest matches the reference. Performance claims must record hardware, OS, compiler/runtime versions, build flags, warmup policy, sample count, and whether startup/translation time is included.

Do not claim Merit is faster, cheaper, safer, or easier to migrate from this harness alone. Those are empirical questions. The purpose of this suite is to make those questions measurable instead of rhetorical.

## Planned implementations

- Merit native project consuming the corpus or generated fixture
- COBOL reference implementation
- Java implementation using explicit `BigDecimal`/domain constraints
- C# implementation using `decimal` plus explicit domain constraints
- Rust implementation using an exact fixed-point representation
- C/C++ implementation using checked scaled integers or a documented decimal library

## Planned migration metrics

Beyond runtime throughput, comparative reports should capture source LOC, adapter LOC, number of separately configured numeric invariants, build time, incremental build time, binary/runtime footprint, peak memory, diagnostics for seeded defects, and the amount of code that must be trusted outside the language/compiler contract.
