# Post-Alpha.2 Cleanup Ledger

## Objective

Perform the bounded technical-debt cleanup deferred by
`v0.1.0-alpha.2` without broadening Merit language semantics. The first
campaign removes unexplained semantic numeric literals according to
`docs/design/NUMERIC_IDENTIFIERS.md`; adjacent bootstrap, validation, and test
infrastructure defects are tracked separately so they do not become accidental
scope in numeric migrations.

Alpha.2 is the immutable compatibility baseline. Preserve its accepted and
rejected surface, serialized discriminants, native ABI, deterministic output,
ownership behavior, and reference/replacement parity.

## Scope rules

- Do not renumber an established discriminant, status, wire value, ABI value,
  type code, policy code, or sentinel.
- Define symbols at the canonical domain boundary, then migrate consumers.
- Keep Python and Merit bootstrap representations in explicit parity.
- Add compatibility assertions before changing consumers of a stable encoding.
- Do not combine numeric-identifier, call-ABI, performance, ownership, or new
  language work unless the evidence proves they are causally inseparable.
- Do not create a repository-wide constants bag or a new schema framework merely
  to avoid local domain definitions.
- Raw numeric values remain valid at canonical encoding definitions and in tests
  whose purpose is to lock the representation.

## Baseline

- Alpha.2 tag: `v0.1.0-alpha.2`
- Tagged commit: `53699f28f0877483081aed81f6b3488d0cf6ffd5`
- Package version: `0.1.0a2`
- Production compiler: trusted Merit-native replacement for the documented
  Alpha.1 surface
- Independent oracle: Python reference compiler
- Hosted release evidence: Ubuntu/native-Windows full and stage-reproducibility
  gates passed for PR #116

## Numeric-identifier inventory

This is a semantic inventory, not a count of every numeric literal. Counts from
text search are deliberately not closure evidence: ordinary arithmetic,
capacities, widths, offsets, and representation-locking tests are not debt merely
because they contain numbers.

| ID | Domain and canonical owner | Concrete existing consumers | Classification | Migration boundary |
|---|---|---|---|---|
| N1 | Lexer token kinds and character bytes; `tokens.mrt` / `lexer.mrt` | `native_replacement_driver.mrt` compares token kinds `1`/`4`, bytes `102`/`110` for `fn`, and braces `123`/`125`; `lexer.mrt` contains the corresponding scanner values | Partly symbolic definition, raw native consumers | Introduce/use token and byte symbols in native lexer/discovery; retain explicit ASCII values only at the canonical encoding definition and lock parity |
| N2 | CST/AST expression and declaration kinds; `syntax.mrt` | `syntax.mrt` uses raw kind sets/ranges including `30..45`, `50`, `51`, `60`, `61`, `70`; `merit/bootstrap/ast_contract.py` still has a raw `kind == 33` consumer | Shared semantic discriminants duplicated across Merit/Python | Establish named canonical kind functions/constants and representation tests, then migrate semantic predicates without changing values |
| N3 | HIR node kinds, type codes, and numeric policies; `hir.mrt` | `hir.mrt` has the densest raw kind comparisons (43 heuristic matches); `merit/bootstrap/hir_parity.py` has named local constants while native consumers such as `mir_source_ownership_expression.mrt` still compare raw HIR kinds | Canonical mapping exists only in pieces | Consolidate domain-owned HIR symbols and prove Python/native parity before consumer migration |
| N4 | MIR expression/function/instruction kinds; `mir*.mrt` | Raw comparisons occur in `mir.mrt`, `mir_composite.mrt`, `mir_functions.mrt`, `mir_statement_lowering.mrt`, and `merit/bootstrap/mir_function_assembly_parity.py`; some later kinds already use helpers such as `function_mir_kind_struct_construct()` | Mixed symbolic and raw semantic discriminants | Complete the existing symbolic pattern by MIR subdomain; preserve snapshot encodings and source order |
| N5 | CFG, structured-control, placement, and ownership event/record kinds | `mir_cfg_parity.py` compares `10`, `11`, `12`, `13`, `14`, `15`, `16`; `mir_ownership_flow.mrt` mixes named ownership helpers with raw event/frame/record kinds such as `20..42` | Cross-language control/lifecycle identifiers | Migrate CFG and ownership families independently with focused control-flow and exact-once cleanup parity tests |
| N6 | Bootstrap error/status codes and nested status offsets | Hundreds of raw `return N;` sites are concentrated in `mir_source_function_records.mrt`, `lexer.mrt`, `statements.mrt`, and `mir_functions.mrt`; named wrappers still embed offsets such as `370`, `1370`, `2090`, `3000`, and `5000` | Contractual statuses, not ordinary arithmetic | Inventory each status namespace first; name established values and offsets without renumbering; retain negative/fail-closed expectations |
| N7 | Sentinels and absence encodings | `-1` and `0` represent absent nodes/bindings/results in HIR, MIR, snapshot rows, and ownership records, but also occur as ordinary bounds/counts | Context-dependent sentinel debt | Define domain-specific sentinels only where numeric absence is contractual; do not replace arithmetic zero/negative one mechanically |
| N8 | Snapshot/bundle framing and row layout | `SNAPSHOT_MAGIC`, `SNAPSHOT_VERSION`, `BUNDLE_MAGIC`, and `BUNDLE_VERSION` are already named; row-width/index consumers remain in `resolved_source_function_snapshot.py` and native snapshot emitters | Canonical representation boundary, mostly compliant | Audit duplicated row indices and add names where semantic; do not hide or renumber canonical wire values |
| N9 | Backend result tags, type-code ranges, and policy encodings | `mir_to_c.py` emits raw Result tags `0`/`1`; `mir_function_assembly_parity.py` already names several type-code bases/strides | ABI/encoding boundary plus raw consumers | Define symbols beside canonical enum/type metadata and preserve generated C, public headers, and ABI fixtures byte-for-byte where required |
| N10 | Test fixtures asserting serialized values | Bootstrap and project tests intentionally compare raw rows, kinds, statuses, and versions | Compatibility evidence, generally not debt | Keep raw assertions when the number is the contract; semantic tests should consume symbols after each domain migration |

The initial search also found many legitimate structural literals: vector
capacities, row widths, field indices, increments, empty/non-empty checks, and
numeric test data. They are excluded unless a focused audit proves hidden domain
meaning.

## Other deferred debt

| ID | Defect | Evidence | Boundary |
|---|---|---|---|
| D1 | Large bootstrap call/status corruption | `ALPHA2_CLOSURE.md` records that one additional scalar argument to `print_resolved_source_function_snapshot` preserved serialized output but corrupted returned status `1392`/wrapped `4392` | Dedicated call-ABI regression and repair; do not fold into numeric-status naming |
| D2 | Repeated native bootstrap construction dominates test time | Historical measurements and gate durations show many project/bootstrap cases pay roughly one native frontend build per isolated process | Test/build infrastructure PR; preserve coverage and clean-build evidence |
| D3 | Pytest cache permission warnings on the WSL checkout | Local focused and full gates repeatedly report inability to write `.pytest_cache` | Environment/test-infrastructure fix; do not weaken tests |
| D4 | Stale transition documentation | Alpha.2 was tagged after its candidate documentation merged | This inventory PR performs only the factual post-release handoff; historical ledgers remain historical |

## Ordered PR queue

1. **Inventory and handoff** — establish this ledger and mark Alpha.2 released;
   no semantic literal migration.
2. **Lexer/token/character identifiers (N1)** — smallest end-to-end domain with
   direct Python/native corpus parity.
3. **CST/AST and HIR identifiers (N2-N3)** — canonical definitions plus parity,
   split only if one combined review cannot remain coherent.
4. **MIR identifiers (N4)** — migrate expression/function/instruction consumers
   while locking snapshot values.
5. **CFG and ownership identifiers (N5)** — preserve source order, cleanup, move,
   drop, and control-flow semantics.
6. **Status namespaces (N6)** — name one bounded status family per coherent PR;
   never renumber or collapse diagnostic distinctions.
7. **Sentinel and representation audit (N7-N10)** — migrate only proven semantic
   consumers; explicitly close compliant boundary/test occurrences as retained.
8. **Deferred defects (D1-D3)** — independently bisectable call-ABI and
   infrastructure repairs after numeric migrations no longer obscure them.
9. **Campaign audit** — prove no unexplained semantic numeric consumer remains,
   all retained raw values are classified, and full cross-platform gates pass.

## Per-PR evidence

Each migration PR must provide:

1. the exact numeric domain and canonical definition site;
2. a before/after consumer inventory;
3. representation assertions proving no value changed;
4. focused Python/native parity or fail-closed tests;
5. confirmation that language semantics, serialization, and ABI did not change;
6. the narrowest relevant subsystem gate, followed by the full gate only when
   the candidate is ready.

## Exit criteria

The cleanup campaign closes when:

- every N1-N10 domain is migrated or explicitly classified as a canonical
  representation/compatibility boundary;
- Python and Merit bootstrap mappings have parity evidence;
- no established discriminant, status, wire value, ABI value, or sentinel was
  renumbered;
- D1-D3 are fixed or moved into a reviewed successor ledger with concrete
  reproducer/evidence;
- status, roadmap, and development instructions identify the next product
  frontier;
- Ubuntu and native-Windows authoritative gates pass.

Only after this bounded campaign should `ALPHA3_CLOSURE.md` define ownership
hardening, allocator-aware buffers/views, and tensor foundations.
