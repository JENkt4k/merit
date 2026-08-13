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

## Reference runner

`run_reference.py` validates the corpus and emits one JSON object containing corpus identity, final state, ordered outcomes, a timing-independent semantic SHA-256, and informational local timing.

```bash
python benchmarks/modernization/run_reference.py
python benchmarks/modernization/run_reference.py --json
```

## Executable comparison v1

The first cross-language slice contains two generated implementations derived from the same frozen JSON corpus:

- `merit/` — native Merit exact decimal `USD(18,2,half_even)`, bounded account/sequence domains, checked arithmetic, interpreter/native parity;
- `java/ModernizationBenchmark.java` — Java `BigDecimal` with explicit decimal literals and comparison/arithmetic calls.

`generate_implementations.py` is the single fixture generator. The repository gate regenerates both sources in memory and requires byte-for-byte equality with the checked-in files. This prevents one implementation from silently changing its transactions, account starting state, or expected ordering.

```bash
python benchmarks/modernization/generate_implementations.py
python benchmarks/modernization/run_comparison.py
python benchmarks/modernization/run_comparison.py --json
```

`run_comparison.py` requires all of the following before producing a report:

1. the generated Merit and Java sources exactly match the frozen corpus;
2. the Merit interpreter output matches Merit native output;
3. Merit output matches the independent Python semantic reference;
4. Java output matches the same independent reference;
5. every implementation has the same timing-independent outcome SHA-256.

The report format is defined by `report_schema_v1.json`.

## Measurement policy

The current comparison records source size, meaningful source lines, build elapsed time, process-run elapsed time, and emitted artifact bytes. These values are **diagnostic measurements**, not a performance ranking. A ten-transaction process invocation is dominated by startup, compiler/runtime state, filesystem cache effects, and measurement noise.

A throughput claim is not eligible until a later benchmark protocol defines in-process repetitions, warmup, sample count, hardware/OS identity, compiler flags, runtime versions, CPU affinity policy where relevant, and statistical reporting. The schema deliberately labels the current measurement scope accordingly.

Correctness eligibility is permanent: no implementation may participate in performance comparisons unless its semantic digest matches the reference.

## Current and planned implementations

| Implementation | Status | Numeric strategy |
|---|---|---|
| Python semantic reference | complete | integer minor units |
| Merit | complete in v1 comparison | language exact decimal + bounded domains |
| Java | complete in v1 comparison | `BigDecimal` + explicit domain logic |
| COBOL | planned | native business decimal / copybook-oriented |
| C# | planned | `decimal` + explicit domain constraints |
| Rust | planned | documented exact fixed-point strategy |
| C/C++ | planned | checked scaled integer or documented decimal library |

## Migration metrics roadmap

Comparative reports should expand beyond runtime throughput to include:

- source LOC and adapter LOC;
- number and location of separately configured numeric invariants;
- clean and incremental build time;
- binary/runtime footprint and peak memory;
- diagnostics for seeded correctness, overflow, ownership, and representation defects;
- amount of migration code trusted outside the language/compiler contract;
- copybook/COMP-3/EBCDIC boundary LOC and generated-vs-handwritten ratio;
- differential behavior against real legacy transaction corpora.

Do not claim Merit is faster, cheaper, safer, or easier to migrate from this harness alone. Those are empirical questions. The suite exists to make them measurable and reproducible rather than rhetorical.
