# COBOL financial modernization example

This project demonstrates a migration shape for transaction-processing code where the primary requirement is not merely translating COBOL syntax, but preserving financial semantics while moving the computation kernel into a native systems language.

## Why this example exists

COBOL financial programs commonly encode business rules around fixed-point decimal fields, bounded identifiers, record layouts, ordered batch processing, and explicit exceptional outcomes. A migration that translates those programs into a general-purpose runtime without making those rules structural can compile successfully while still weakening the guarantees that matter.

Merit makes the important properties visible in the program:

| Concern | Merit mechanism in this example |
| --- | --- |
| Currency must be decimal, never binary floating point | `decimal USD(18, 2, half_even)` |
| Identifiers and sequence values have valid domains | nominal `bounded` integer types |
| External records need a stable ABI | versioned `stable` structs |
| Arithmetic overflow/underflow must not wrap | `checked_add` / `checked_sub` |
| Mutations must satisfy business pre/postconditions | `requires` / `ensures` contracts |
| Duplicate or reordered postings must be explicit | sequence validation and a typed rejection enum |
| Failure cases must be exhaustively handled | payload enums plus `match` |
| Native and reference execution must agree | normal `merit-project verify` differential path |
| Migration cannot require a flag-day rewrite | canonical COBOL-facing bridge records |

## Modules

- `finance_types.mrt` defines the exact numeric domains, stable account/posting/receipt records, and typed outcomes.
- `ledger.mrt` implements a deterministic transfer kernel. All rejection checks occur before account mutation, and the debit/credit helpers carry executable contracts.
- `legacy_bridge.mrt` is the anti-corruption layer between canonical legacy records and the new domain model.
- `main.mrt` simulates a COBOL-originated transfer, processes it in Merit, rejects a duplicate posting, and exports canonical records back toward the legacy side.

## Expected example behavior

The first transfer moves `$125.50` from account `1001001` to account `2002002`:

```text
1124.50
200.75
41
```

The same sequence number is then submitted again and must be rejected. The example prints `1` for `DuplicateOrOutOfOrder`, followed by the unchanged final balances:

```text
1
1124.50
200.75
```

## Migration boundary

`CobolAccountRecord` and `CobolTransferRecord` are **canonical interchange records**, not a claim that every COBOL copybook has this in-memory representation. Real estates frequently use EBCDIC text, zoned decimal, packed decimal (`COMP-3`), binary `COMP`, REDEFINES, OCCURS, and platform-specific alignment.

The recommended migration architecture is therefore:

```text
existing COBOL / copybook bytes
        |
        v
small generated or audited adapter
(EBCDIC + PIC/COMP-3 + copybook mapping)
        |
        v
versioned stable canonical record
        |
        v
Merit exact financial kernel
        |
        +----> generated C ABI / services / modern storage
        |
        v
optional canonical record back to COBOL
```

Keeping encoding and copybook decoding at the edge prevents legacy representation rules from contaminating the financial domain while still allowing program-by-program strangler migration.

## Why not simply translate to Java?

Java can implement correct financial arithmetic with `BigDecimal`, but `BigDecimal` is a library type rather than a language-wide numeric domain. Scale, rounding, conversion, equality behavior, allocation, and the prohibition of binary floating point remain conventions that every code path and reviewer must preserve. A large translated estate can therefore contain both correct and subtly incompatible numeric paths while still being valid Java.

Merit's design makes the financial choice nominal and statically visible: `USD` is an exact fixed-scale type with an explicit rounding policy; numeric domains do not implicitly mix; literals exceeding scale are rejected; and checked arithmetic has matching interpreter/native failure behavior.

This does not make persistence atomic by itself. Production settlement still requires a transactional journal/database or durable log around the kernel. Merit addresses deterministic computation, numeric correctness, resource safety, ABI stability, and migration boundaries; the storage system remains responsible for durable atomic commit.

## Verify

From the repository root:

```bash
merit-project check examples/projects/cobol_finance_modernization
merit-project verify examples/projects/cobol_finance_modernization
merit-project layout examples/projects/cobol_finance_modernization
```

`layout` is especially important during migration because stable-record hashes can be treated as deployment compatibility gates.

## Next library work

The next useful migration layer is a copybook toolkit that parses a constrained copybook subset and generates: (1) byte-level EBCDIC/zoned/COMP-3 decoders, (2) stable Merit canonical records, (3) C headers/shims for coexistence, and (4) golden-vector differential tests against the existing COBOL implementation. That should remain a boundary library rather than weakening Merit's exact numeric core with implicit legacy conversions.
