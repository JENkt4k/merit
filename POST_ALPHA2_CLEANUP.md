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
- Do not intermingle numeric-identifier, call-ABI, performance, ownership, or
  new-language edits inside one implementation stage. A deliberately bounded
  campaign PR may close several separately tracked debt items through ordered,
  independently committed stages with focused validation after each stage.
- Prefer one substantial PR per ledger milestone: use staged local checkpoints
  for bisectability, then pay for one subsystem/full/hosted validation cycle.
  Split a milestone across PRs only for a concrete dependency, release-risk, or
  reviewability reason—not merely because its stages can be tested separately.
- Do not create a repository-wide constants bag or a new schema framework merely
  to avoid local domain definitions.
- Raw numeric values remain valid at canonical encoding definitions and in tests
  whose purpose is to lock the representation.
- At most one successor milestone may be developed as a stacked draft PR while
  its prerequisite PR runs hosted validation. The successor must target the
  prerequisite branch, may not merge first, and must be rebased onto verified
  current `main` and revalidated after the prerequisite merges. Any prerequisite
  failure takes priority.

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
| N1 | Lexer token kinds and character bytes; `tokens.mrt` / `lexer.mrt` | `tokens.mrt` owns all five token-kind values and the structural ASCII alphabet; `lexer.mrt` consumes those symbols throughout scanning/parsing, while `native_replacement_driver.mrt` uses the symbols and shared keyword predicates | Closed: canonical numeric definitions plus interpreter/native representation and production-driver evidence | Explicit values remain only in `tokens.mrt`, canonical keyword spelling/packed-ASCII definitions, and representation-locking tests; N2 owns syntax kinds and packed keyword classification |
| N2 | CST/AST expression and declaration kinds; `syntax.mrt` | `syntax.mrt` uses raw kind sets/ranges including `30..45`, `50`, `51`, `60`, `61`, `70`; `merit/bootstrap/ast_contract.py` still has a raw `kind == 33` consumer | Shared semantic discriminants duplicated across Merit/Python | Establish named canonical kind functions/constants and representation tests, then migrate semantic predicates without changing values |
| N3 | HIR node kinds, type codes, and numeric policies; `hir.mrt` | `hir.mrt` has the densest raw kind comparisons (43 heuristic matches); `merit/bootstrap/hir_parity.py` has named local constants while native consumers such as `mir_source_ownership_expression.mrt` still compare raw HIR kinds | Canonical mapping exists only in pieces | Consolidate domain-owned HIR symbols and prove Python/native parity before consumer migration |
| N4 | MIR expression/function/instruction kinds; `mir*.mrt` | Raw comparisons occur in `mir.mrt`, `mir_composite.mrt`, `mir_functions.mrt`, `mir_statement_lowering.mrt`, and `merit/bootstrap/mir_function_assembly_parity.py`; some later kinds already use helpers such as `function_mir_kind_struct_construct()` | Mixed symbolic and raw semantic discriminants | Complete the existing symbolic pattern by MIR subdomain; preserve snapshot encodings and source order |
| N5 | CFG, structured-control, placement, and ownership event/record kinds | N5a names CFG records and structured-control events/frames; N5b names ownership events, records, lifecycle states, and internal frame kinds | Active: N5a merged; N5b candidate | Migrate CFG and ownership families independently with focused control-flow and exact-once cleanup parity tests |
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

## Completed evidence

### N1 lexer/token/character identifiers

- Canonical owner: `examples/projects/bootstrap_lexer/src/tokens.mrt`.
- Migrated consumers: the complete scanner and parser token-kind/structural-byte
  use in `lexer.mrt`, plus function, enum, capability, and brace discovery in
  `native_replacement_driver.mrt`.
- Shared keyword predicates now prevent the production driver from duplicating
  the ASCII spellings for `fn`, `enum`, and `capability`.
- `test_bootstrap_token_and_character_representation_is_stable` locks all five
  token kinds and the structural ASCII values through both the interpreter and
  generated native C (1 passed in 16.83s).
- `test_bootstrap_lexer_matches_interpreter_native_and_ordered_c` and
  `test_build_concrete_native_driver_reaches_replacement_executable_without_python_semantic_lowering`
  preserve lexer oracle parity and the production replacement path (2 passed in
  34.92s).
- Focused multi-function, capability-catalog, and payload-free-enum catalog
  driver cases preserve all three shared keyword-discovery paths (3 passed in
  17.09s).
- The complete bootstrap lexer file preserves accepted/rejected corpus,
  expression precedence, allocation capability checks, interpreter behavior,
  and native C parity (29 passed in 411.72s).
- The bootstrap/project subsystem gate passes with the N1 migration (419 passed,
  1 skipped in 1087.38s; gate duration 1089.86s).
- The authoritative local full gate passes with 1152 tests passed, 1 skipped,
  all 10 replacement acceptance projects verified, and a total duration of
  2285.551s.
- Retained raw values in packed keyword matching are canonical encoding
  definitions; syntax node kinds, diagnostics/statuses, and their consumers are
  intentionally assigned to N2 and N6 rather than expanded into this PR.

### N2-N3 CST/AST and HIR identifiers (closed by PR #119)

- Canonical owners: `bootstrap_syntax` now defines every top-level declaration,
  clause, statement-envelope, and expression AST kind; `bootstrap_hir` defines
  every HIR node kind, primitive type code, numeric policy, and operator symbol.
- Python mirrors in `ast_contract.py`, `ast_parity.py`, `hir_parity.py`, and
  `hir_string_parity.py` consume named mappings rather than duplicating raw
  semantic values.
- Native lowering consumers in lexer discovery, HIR construction/validation,
  statement lowering, function contracts, source-function assembly, and
  ownership expression lowering now reference domain-owned symbols or semantic
  predicates. A focused audit finds no remaining direct raw comparisons against
  `ast_kind(...)` or `hir_kind(...)`.
- `test_bootstrap_ast_hir_identifier_representation_is_stable` locks the complete
  mapping through both the interpreter and generated native C (1 passed in
  15.43s after the final naming correction).
- The focused Python/native AST/HIR suite passes with 51 tests in 47.01s.
- Typed statement-operand and real source-function assembly parity preserve the
  downstream production path (2 passed in 35.93s).
- Raw values remain in canonical definitions and representation-locking fixtures;
  status values, sentinels, MIR kinds, and ownership record kinds remain assigned
  to N4-N7.
- The bootstrap/project subsystem gate passes with 420 tests passed and 1
  skipped in 1060.88s (gate duration 1063.299s).
- The authoritative local full gate passes with 1155 tests passed, 1 skipped,
  all 10 replacement acceptance projects verified, and a total gate duration of
  2297.298s.
- PR #119 merged as `c1e7fcbdb4c0afe7aebd98e9593805f7e3bb0461`
  after Ubuntu/native-Windows full gates, both M9 reproducibility gates, corpus
  convergence, and replacement acceptance all passed.

### N4 MIR identifiers (closed by PR #120)

- Canonical Merit owners now name the established expression, composite,
  whole-function, generic-call, function-contract, and assembled-instruction
  source kinds in their corresponding `bootstrap_mir*` modules.
- Constructors, validators, source-function consumers, contract assembly, and
  Python reconstruction use those symbols instead of duplicating raw semantic
  discriminants. CFG terminator kinds and structured-control/ownership frame
  kinds remain assigned to N5; statuses and sentinels remain assigned to N6-N7.
- Python mirror constants provide one named representation surface for the
  expression, composite, generic, whole-function, contract, and instruction
  source record families. `test_python_mir_kind_mirrors_preserve_bootstrap_encodings`
  locks their existing numeric assignments (included in 127 focused tests that
  passed in 7.71s).
- `test_bootstrap_mir_kind_representation_is_stable` locks the same Merit-side
  assignments through both the interpreter and generated native C (1 passed in
  16.49s).
- Primitive, composite, generic, and straight-line function production parity
  each pass independently (1 test each in 16.71s, 16.96s, 17.18s, and 17.60s).
  Real source-function contract/CFG assembly also passes (1 test in 22.05s),
  and the focused contract suite passes (44 tests across direct and native
  project evidence).
- No record value, source order, serialization, ABI value, or language semantic
  behavior changed. Raw values remain only at canonical representation
  definitions, representation-locking fixtures, or domains reserved for N5-N10.
- The bootstrap/project subsystem gate passes with 421 tests passed and 1
  skipped in 1116.66s (gate duration 1119.946s).
- The authoritative local full gate passes with 1157 tests passed, 1 skipped,
  all 10 replacement acceptance projects verified, and a total gate duration
  of 2392.375s.
- PR #120 merged as `be5b7def3327cb235a48d93f59c66bcab4620f92`
  after Ubuntu/native-Windows full gates, both M9 reproducibility gates, corpus
  convergence, and replacement acceptance all passed.

### N5a CFG and structured-control identifiers (closed by PR #121)

- Canonical Merit owners now name all established CFG record kinds in
  `bootstrap_mir_cfg` and all structured-lowering event kinds in
  `bootstrap_mir_structured_lowering`. Internal structured-lowering and
  statement-lowering frame kinds are named locally at their definition sites.
- CFG constructors, structured-control lowering, whole-function event assembly,
  ownership-aware event assembly, and Python canonical-MIR reconstruction now
  consume those symbols instead of duplicating their numeric discriminants.
- `mir_cfg_parity.py` exposes the matching Python constants, and
  `test_python_cfg_kind_mirrors_preserve_bootstrap_encodings` locks the existing
  `10..16` representation (included in 29 direct CFG/control-flow tests that
  passed in 0.81s).
- `test_bootstrap_cfg_structured_kind_representation_is_stable` locks all CFG
  and structured-event values through both the interpreter and generated native
  C (1 passed in 17.12s).
- Structured lowering and resolved source control flow preserve native behavior
  (3 passed in 33.64s); statement lowering and whole-function contract/CFG
  assembly pass (3 passed in 32.10s); direct whole-function adapters pass
  (8 passed in 1.15s).
- Source ownership and ownership-flow production gates preserve the adjacent
  exact-once lifecycle path (4 passed in 33.94s). Ownership event, frame, and
  record discriminants remain deliberately assigned to N5b.
- No record value, source order, serialization, ABI value, ownership behavior,
  or language semantic changed. Placement has no numeric kind domain and was
  validated through the same production paths rather than given an artificial
  identifier family.
- The bootstrap/project subsystem gate passes with 422 tests passed and 1
  skipped in 1112.87s (gate duration 1115.417s).
- The authoritative local full gate passes with 1159 tests passed, 1 skipped,
  all 10 replacement acceptance projects verified, and a total gate duration
  of 2402.905s.
- PR #121 merged as `7ff3d1ad3fe70596c077610fe35e345552bbee7b`
  after Ubuntu/native-Windows full gates, both M9 reproducibility gates, corpus
  convergence, and replacement acceptance all passed.

### N5b ownership identifiers (candidate)

- `bootstrap_mir_ownership_flow` now canonically names all established
  ownership event and output-record discriminants, lifecycle states, and its
  internal if/while/match frame kinds. Source ownership control likewise names
  its internal if/while frame kinds.
- Ownership constructors, validation, state transitions, control-flow merging,
  whole-function assembly, and the Python canonical-MIR adapter consume those
  symbols without changing any encoded value.
- `test_bootstrap_ownership_kind_representation_is_stable` locks the complete
  public Merit event/record/state representation through both the interpreter
  and generated native C (1 passed in 17.10s). The Python representation test
  locks matching record and lifecycle constants.
- Direct cleanup and ownership assembly tests pass (30 passed in 2.78s).
  Ownership-flow and source-ownership project gates pass (4 passed, longest
  file 19.14s), and resolved/derived source ownership remains green (2 passed,
  longest file 19.60s).
- No event, record, lifecycle, serialization, ABI, source-order, cleanup, move,
  drop, or control-flow semantic changed. Status values, sentinels, and
  representation-boundary raw values remain assigned to N6-N10.
- The bootstrap/project subsystem gate passes with 423 tests passed and 1
  skipped in 1087.67s (gate duration 1090.03s).
- The authoritative local full gate passes with 1160 tests passed, 1 skipped,
  all 10 replacement acceptance projects verified, and a total gate duration
  of 2442.287s.
- Hosted cross-platform and merge evidence remain pending.

## Ordered PR checklist

- [x] **Inventory and handoff (PR #117)** — establish this ledger and mark
  Alpha.2 released; no semantic literal migration.
- [x] **Lexer/token/character identifiers (N1, PR #118)** — canonical token and
  character definitions with direct Python/native and replacement-driver
  parity.
- [x] **CST/AST and HIR identifiers (N2-N3, PR #119)** — canonical definitions
  plus Python/native representation and production-path parity.
- [x] **MIR identifiers (N4, PR #120)** — migrate expression/function/instruction
  consumers while locking snapshot values.
- [ ] **CFG and ownership identifiers (N5, active)** — N5a CFG and structured
  control closed in PR #121; N5b ownership is the current candidate. Preserve
  source order, cleanup, move, drop, and control-flow semantics.
- [ ] **Deferred defects (D2, D3, then D1)** — one staged PR: first remove
  redundant native-bootstrap construction, then repair WSL pytest-cache
  handling, then reproduce and repair the independently testable call-ABI
  corruption. Preserve clean-build coverage and commit each stage separately.
- [ ] **Status namespaces (N6)** — one staged milestone PR covering the bounded
  status families; never renumber or collapse diagnostic distinctions.
- [ ] **Sentinel and representation audit (N7-N10)** — one combined audit PR;
  migrate only proven semantic consumers and explicitly retain compliant
  boundary/test occurrences.
- [ ] **Campaign audit** — prove no unexplained semantic numeric consumer
  remains, all retained raw values are classified, documentation identifies the
  next product frontier, and full Ubuntu/native-Windows gates pass.

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
