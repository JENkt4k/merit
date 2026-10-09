# SH3 capability matrix

This is the authoritative **SH3 burn-down** under the scope and exit contract
in `SELF_HOSTING.md`. It is not an Alpha.3 plan. Update a row only after its
stated evidence runs against the current tree; a later tree change makes the
affected evidence stale. Do not replace a family with a sequence of one-project
fixes or mark a family complete because one probe advances to a later error.

## Baseline and comparison boundary

- Inventory baseline: committed branch `self-hosting/sh3-native-mir-backend` at
  `db41df3`. The later SH3 checkpoint is `e12f1f9`. The catalog-aware MIR type writer is **not** included
  in the acceptance runtime results below. A focused direct test now compares
  builtin, nested vector, copy/owned-payload enum, owned-field struct,
  stable-ABI aggregate, decimal, bounded, and legacy scalar-struct JSON
  against the Python snapshot oracle; cyclic graphs and invalid decimal
  metadata reject. Full function/project materialization remains unproved.
- Authoritative independent implementations: snapshot/type materialization in
  `merit/bootstrap/resolved_source_function_snapshot.py`; project assembly in
  `merit/bootstrap/replacement_project.py`; deterministic C and public header
  emission in `merit/bootstrap/mir_to_c.py`; normal project artifact selection
  and publication in `merit/project/replacement.py` and
  `merit/project/replacement_prepare.py`.
- Native path being closed: `examples/projects/bootstrap_lexer/src/` source and
  the `emit_native_project_artifacts` entry in `native_replacement_driver.mrt`.
  The v4 response already transports canonical MIR, C, and header bytes, but
  the complete Alpha.2 surface has not been proved.
- The ten projects below were sent as MPRQ v1 requests to the already-built
  `db41df3` v4 executable. Each ordinary request finished within 20 seconds.
  The compiler project exceeded the diagnostic cap and was terminated; it
  remains **unknown**, not failed. This was not a canonical gate. Do not repeat
  a capped long-running compiler-project probe; arrange uninterrupted/manual
  execution with a log when that boundary is ready.

| Acceptance project | v4 baseline | Earliest observed family |
| --- | --- | --- |
| `text_pipeline` | status `4409` | F6: borrowed-`Buffer` public helper cannot be selected as a C ABI export; MPRQ v1 lacks header intent |
| `binary_packet` | status `4129` | F1: canonical MIR local type graph |
| `generic_result` | status `4129` | F1: canonical MIR local type graph |
| `trait_bounds` | status `4129` | F1: canonical MIR local type graph |
| `generic_collections` | status `4129` | F1: canonical MIR local type graph |
| `borrowed_views` | status `4129` | F1: canonical MIR local type graph |
| `bootstrap_lexer` | unknown after 20 seconds | F8/F9: complete compiler source and throughput remain unmeasured |
| `cobol_finance_modernization` | status `4129` | F1: canonical MIR local type graph |
| `filesystem_capabilities` | status `4129` | F1: canonical MIR local type graph |
| `ledger_app` | status `4107` | F2: canonical CFG block ordinal/topology precedes type writing |

These first failures do **not** prove later families work. The accepted/rejected
corpus, compiler project, and complete output-byte comparisons have not been
run through v4. Status offsets are from the native driver's named status
wrappers, not new diagnostic meanings.

### Fresh uncommitted F1/F2 candidate diagnostic

The existing black-box v4 artifact test passed on the F1/F2 candidate tree
(`1 passed in 47.33s`) after the native Windows GCC environment was activated.
Its newly built compiler executable then received all ten MPRQ v1 acceptance
requests without timeouts. Every request advanced past the old `4129`
type-graph or `4107` CFG failure; none completed. A later uncommitted scalar
C spelling change means this sweep is no longer evidence for the exact latest
tree. These are **first failures only**, not evidence that F1/F2 or an
acceptance project is complete.

| Project | Candidate status | Earliest remaining mechanism indicated by the status |
| --- | --- | --- |
| `text_pipeline` | `4409` | F6, public-header selection/borrowed-`Buffer` export, as at baseline |
| `binary_packet` | `4473` | F5, backend call parameter type subset (`canonical_c_append_function_core_ordered` status 73) |
| `generic_result` | `4492` | F5, backend switch/terminator-row shape (status 92) |
| `trait_bounds` | `4410` | F4/F5, backend local type/resource coverage (status 10) |
| `generic_collections` | `4492` | F5, backend switch/terminator-row shape |
| `borrowed_views` | `4410` | F4/F5, backend local type/resource coverage |
| `cobol_finance_modernization` | `4403` | F4, backend return type/layout subset (status 3) |
| `filesystem_capabilities` | `4492` | F5, backend switch/terminator-row shape |
| `ledger_app` | `4492` | F5, backend switch/terminator-row shape; prior `4107` no longer first failure |
| `bootstrap_lexer` | `4409` | F6, public-header selection; request finished in 39.08s |

### Latest uncommitted typed-constant/CFG candidate diagnostic

The same v4 black-box test passed on the later F1/F2/F5 tree (`2 passed in
85.89s` for the native entry and adjacent contract regression). Its freshly
built executable completed all ten MPRQ v1 requests. The response failure
marker remained `0` in each case; the native process exit codes below are the
first failure statuses. This is a diagnostic sweep, not artifact parity or an
acceptance gate. The previous `4492` switch-row failures advancing to `4410`
support the CFG normalization direction but do not close F5.

| Project | Latest first failure | Matrix family |
| --- | --- | --- |
| `text_pipeline` | `4409` | F6 header intent/export |
| `binary_packet` | `4473` | F5 call parameter coverage |
| `generic_result` | `4410` | F4/F5 local type/resource coverage |
| `trait_bounds` | `4410` | F4/F5 local type/resource coverage |
| `generic_collections` | `4410` | F4/F5 local type/resource coverage |
| `borrowed_views` | `4410` | F4/F5 local type/resource coverage |
| `bootstrap_lexer` | `4409` | F6 header intent/export |
| `cobol_finance_modernization` | `4403` | F4 return type/layout coverage |
| `filesystem_capabilities` | `4410` | F4/F5 local type/resource coverage |
| `ledger_app` | `4410` | F4/F5 local type/resource coverage |

### Post-checkpoint fixed-integer admission diagnostic

On checkpoint `e12f1f9`, the focused v4 native-entry artifact/oracle test
passed (`1 passed in 49.24s`). Its newly built executable then received the
ten MPRQ v1 acceptance requests. The fixed-integer local-admission change did
not advance the nine ordinary first-failure statuses: `text_pipeline` `4409`,
`binary_packet` `4473`, `generic_result` `4410`, `trait_bounds` `4410`,
`generic_collections` `4410`, `borrowed_views` `4410`,
`cobol_finance_modernization` `4403`, `filesystem_capabilities` `4410`, and
`ledger_app` `4410`. The `bootstrap_lexer` request exceeded the 25-second
diagnostic cap and is **unknown**, not failed. No acceptance pass or complete
artifact comparison is claimed. A read-only decode of the successful legacy
native bundle for `trait_bounds` identified concrete type code `1200000` in
its first function's parameter and source-local rows, with an aggregate-struct
descriptor `(1200000, 3, 0, 7, 0, 0, 61, 5, 73, 1, 2)` for stable `Point`.
The C backend admits neither the parameter nor local aggregate code and
`canonical_c_append_type_with_catalog` has no aggregate spelling or typedef
path. This is a verified F4 mechanism; it does **not** imply that adding a
whitelist entry alone would make the project pass.

### Current aggregate-family candidate

The native aggregate C spelling now requires a valid descriptor and matches
the Python oracle for stable `Point` (`1 passed in 31.62s`). A dependency-
ordered typedef writer matches the oracle's nested integer-aggregate form
(`1 passed in 31.59s`). The production module finalizer collects aggregate
types reached from function return/parameter/local records and their nested
aggregate fields, emits those typedefs before prototypes, and admits validated
aggregate locals. The focused v4 native-entry regression passed on that tree
(`1 passed in 66.90s`). A four-project candidate sweep then moved
`trait_bounds` and `borrowed_views` from `4410` to `4414`, the explicit
unsupported-instruction branch; `generic_result` stayed `4410` and
`cobol_finance_modernization` stayed `4403`. These are first-failure statuses,
not accepted projects. Aggregate construct/load/store,
destructor cleanup, non-integer fields, nested enums/vectors, and stable public
header layout remain open in F4/F5/F6. The subsequent parameter-admission and
aggregate local zero-initialization edit passed the focused v4 native-entry
regression (`1 passed in 60.35s`), but its acceptance statuses have not been
reswept.

The aggregate instruction slice now validates and lowers integer/bool-field
construct, load, and initializing store by descriptor ordinal and concrete
local type. A catalog-validated aggregate with only Copy scalar fields and no
destructor has explicit move and drop lowering; other lifecycle graphs remain
fail-closed. The stable `Point` black-box fixture produces native v4 MIR/C/header
artifacts, exact Python-oracle C/header bytes, GCC compilation, and the expected
runtime result (`1 passed in 62.35s`). The dependency-order test also rejects
a cyclic aggregate graph (`1 passed in 31.63s`). A preceding candidate advanced
`trait_bounds` to `4473` (call parameter coverage) and `borrowed_views` to
`4461` (call/result coverage), while `generic_result`,
`generic_collections`, `filesystem_capabilities`, and `ledger_app` stayed at
`4410`. Those statuses predate the final trivial-aggregate drop edit and are
diagnostic only. The complete aggregate family still needs non-scalar fields,
replace cleanup, recursive ownership, stable public-header layouts, and
project-level call coverage; neither F4 nor F5 is marked closed.

### Aggregate-boundary regression run (Windows)

The manually run aggregate boundary selection reported `46 failed, 242 passed,
1 skipped` in 8979.94 seconds. This is diagnostic, not gate evidence: 42 failures
were the same environment precondition (`shutil.which("cc") or
shutil.which("gcc")` returned `None`). PowerShell had blocked the unsigned
activation script, leaving GCC off pytest workers' `PATH`. The remaining four
were reproduced independently. The comparison-result rejection now preserves
its `77` diagnostic before the generic type mismatch; a borrowed parameter
cannot be returned as a value-mode result (`24`); and the shared
`bootstrap_buffer_append` fixture passes `buffer_len` its required borrowed
argument rather than a value-mode argument (`68`). Their focused selection
passed 9 of 10 cases in 295.56 seconds, with the sole failure again being
missing GCC. After setting process-scoped execution-policy bypass and checking
`shutil.which("gcc")`, that GCC-backed case passed in 16.77 seconds. The broad
run must not be represented as passing, and no full gate has run on this tree.

A nested `Inner`/`Outer` probe initially exposed the backend's scalar-only
field guard (`4521` after correcting a missing field in the probe). F4 now
admits a recursively nested aggregate only when every leaf is an integer/bool
Copy field, no field has a destructor policy, and the descriptor graph remains
within a bounded depth. Construct/load/store and explicit move/drop share that
admission check; the drop writer emits the oracle's no-op statement for each
scalar leaf. The v4 artifact test then passed exact Python C/header bytes and
GCC runtime (`1 passed in 51.89s`, rerun on the final tree:
`1 passed in 51.44s`). Two direct descriptor tests passed on that tree
(`2 passed in 62.89s`; the other tests were deselected by the focused filter).
Owned nested fields and destructors remain
fail-closed, not implicitly copied.

The binary-safe MPRQ v1 sweep against the aggregate focused-test executable
finished all nine non-compiler acceptance requests in 2.6 seconds. The table
also incorporates the later targeted `binary_packet` resweep after vector
dispatch/drop repair. These are first-failure diagnostics only; none is
accepted or oracle-equivalent yet.

| Project | Current first status | Shared next mechanism |
| --- | --- | --- |
| `text_pipeline` | `4409` | F6 public-header selection / unsupported exported parameter |
| `binary_packet` | `4409` after vector dispatch/drop repair | F6 public-header selection |
| `trait_bounds` | `4473` | F5 aggregate user-call parameter coverage |
| `generic_result`, `generic_collections`, `filesystem_capabilities`, `ledger_app` | `4410` | F4 source-local type/layout coverage |
| `borrowed_views` | `4461` | F5 call/result coverage |
| `cobol_finance_modernization` | `4403` | F4 return type/layout coverage |

`ledger_app` has advanced from the committed-baseline `4107` canonical CFG
failure to the common `4410` backend type boundary. That is evidence of F2
progress, not F2 completion. The compiler project remains unmeasured at this
candidate boundary.

Temporary diagnostics at all three `4410` exits (removed immediately after
the sweep) showed that all four projects take the unsupported catalog type
branch, not the missing-ownership-record branches. `generic_result` reaches
Copy-payload enum type code `1000`; `filesystem_capabilities` and `ledger_app`
reach Copy-payload enum code `1001`; `generic_collections` reaches owned-field
struct code `1000000`. Thus F4 needs two explicit, descriptor-validated C type
families, not a relaxation of the ownership precondition. The first family
must emit the oracle's ordered Copy-payload enum typedefs and initializer,
then support construct/load/match and calls; the second needs the owned-field
struct typedef and lifecycle/effect lowering. Until those vertical mechanisms
are represented, the backend must continue to reject these requests.

A second temporary diagnostic build (also reverted) classified the other
backend boundaries: `binary_packet`'s `4473` is an `Allocator` call parameter
(`3`); `trait_bounds`'s `4473` is an aggregate call parameter (`1200000`);
`borrowed_views`'s `4461` is an aggregate call result (`1200000`); and
`cobol_finance_modernization`'s `4403` is a decimal return type (`1300000`).
These are F5 call typing plus F4 aggregate/numeric representation, not four
independent project defects. The remaining type-family order is: descriptor-
validated enum/owned-field/numeric C representations, then shared call
parameter/result admission and ownership-mode evidence. `Allocator` already
has C spelling, so its call admission should be tested as a narrow supported
builtin while keeping exported ABI rules intact.

That bounded `Allocator` user-call admission now has v4 MIR/C/header oracle and
GCC output evidence (`1 passed in 37.29s`). `binary_packet` still reports
`4473`: a subsequent temporary diagnostic (removed) identified concrete
vector parameter code `1500000`. This is the shared F5 vector builtin/call
family, not another missing `Allocator` case. The native backend had separate
`new/push/len` and `get/set/replace/pop/allocator` paths, but callable-catalog
lookup took precedence over those builtin paths for synthesized concrete
specializations. The oracle gives vector builtins priority. The dispatch now
does likewise; unsupported `vec_transfer` still fails closed. A focused
four-case vector new/push/len/drop selection plus v4 artifact regression passed
(`5 passed in 181.54s`). `binary_packet` then reached `4465`, identified as
`vec_drop__i64`. Its snapshot requires a unit call with mutable-borrow mode;
the native backend now emits the vector drop helper under that exact contract,
while preserving the subsequent explicit cleanup effect. A source-backed v4
regression passed exact Python C/header bytes and GCC output
(`1 passed in 40.06s`). `binary_packet` now advances to `4409`, the existing
F6 header-selection boundary. These results do not close all vector semantics:
owned elements and `vec_transfer` remain outside the proven subset.

The first descriptor-validated Copy-payload enum C case now matches the
Python oracle's v4 MIR/C/header bytes and GCC output for construct, tag/payload
load, and match (`1 passed in 52.10s`). This is F4 subset evidence, not project
closure. A diagnostic sweep found `generic_result` now stops at `4101` in its
second function. Temporary instrumentation, subsequently removed, showed
`validate_function_mir_records` returns `6`: its record sequence contains two
return records. The second function is `max_value`, whose two branches each
return. The linear record validator rejects any record following a return,
before CFG placement can establish that the two returns occupy separate
blocks. This is an F2 multiple-terminator representation dependency. The
previous candidate reached `4410`; the changed first-failure order must not
be mistaken for proof of a new enum defect or for F2 closure. Resolve the
record/CFG validation contract with an explicit two-return differential
fixture before claiming `generic_result` backend progress. Other enum-bearing
projects still stop at `4410` and require catalog/descriptor diagnostics.

The sourced-CFG validator now admits multiple individually validated return
records without changing the straight-line validator. A new v4 two-branch
regression exposed native C serialization of an unreachable synthetic block
(`b3: abort();`) that the canonical Python MIR/C path prunes. The C backend
now uses the same reachable-block selection as canonical MIR and counts only
placements in emitted blocks; it still validates all CFG terminators before
emission. The focused v4 test passes exact MIR/C/header comparison and GCC
runtime output on Windows (`1 passed in 38.71s`). This establishes the
two-return subset, not full F2/F5 closure; broader malformed CFG and accepted
project evidence remain required.
The next `generic_result` status, `4102`, was an unsourced parameter-only
`copy_value` function: header, parameter, return, and no instruction
placements. The materializer now admits the validated no-placement shape by
header parameter count while keeping the one-placement path restricted. A
source-backed identity fixture passes, and the full `generic_result` request
now returns a v4 artifact whose generated C/header exactly match the Python
emitter from that artifact's parsed MIR, and its generated C compiles and
prints the expected two `42` lines. The separate native legacy snapshot
entrypoint supplies all three function snapshots; independent Python project
materialization matches the v4 canonical MIR byte-for-byte. The durable
focused test passes these MIR/C/header/runtime comparisons together
(`1 passed in 42.24s`). This is one acceptance project, not F8 closure for
the remaining applications, rejected corpus, or compiler project.

The next ten-project v4 first-status sweep on this candidate returned:
`text_pipeline 4409`, `binary_packet 4409`, `generic_result 0`,
`trait_bounds 4473`, `generic_collections 4410`, `borrowed_views 4461`,
`bootstrap_lexer 4424`, `cobol_finance_modernization 4403`,
`filesystem_capabilities 4410`, and `ledger_app 4410`. This preserves the
finite grouping: F6 header intent (two), F4 type/runtime representation
(owned-field/numeric/enum-bearing projects), F5 call mode/result (two), and
the compiler-project backend boundary. No broad gate follows this sweep.
The saved legacy snapshot for `filesystem_capabilities` shows both a Copy
payload enum (`1001`, descriptor kind `5`) and an owned-payload enum
(`1100000`, descriptor kind `2`) as locals. The remaining `4410` is therefore
not evidence that the newly supported Copy enum spelling is broken; the
owned-payload family still needs its representation and explicit resource
effects. Keep owned enum/owned-field struct lifecycle together as F4/F5 work
instead of admitting the type spelling alone.

The shared F5 user-call admission now accepts descriptor-validated Copy
aggregates in value mode, without admitting owned or borrowed aggregate modes
through that shortcut. `trait_bounds` produces v4 MIR/C/header bytes matching
the independent legacy-snapshot/Python project oracle and GCC output `17`
(`1 passed in 54.12s`). The differential test exposed and corrected an F2
ownership omission: native MIR serialization now applies validated ownership
binding rows to parameter locals, as the Python oracle does, so an owned
`Point` parameter is not mislabeled `value`. `borrowed_views` advances from
`4461` to `4462`; its borrowed/mutable-borrow aggregate result modes are a
distinct pointer-ABI family requiring end-to-end evidence. Value-mode
aggregate calls are proved only for this subset, not all F5 calls.

The borrowed/mutable-borrow aggregate result path is now represented in
canonical MIR and C: pointer-typed locals, prototypes, relay returns, call
forwarding, and field access use the existing Alpha.2 modes. A shared
source-token visibility check also makes callable catalog names agree with
exported function definitions across modules. `borrowed_views` native MIR is
byte-identical to independent legacy-snapshot/Python materialization (6,770
bytes), and generated C matches the Python emitter. The saved native C
artifact compiles under UCRT64 GCC and prints `5` then `8`. The focused end-to-end
test initially exposed F6 public-header parity: the native header used
internal `merit_struct_aggregate_0`, while the oracle required stable public
`merit_Record` and size/offset assertions. That failure was repaired below.

The native public-header finalizer now derives exported signatures from the
same source-backed callable catalog, uses descriptor-validated public/stable
aggregate names, orders nested layout dependencies, and emits exact size and
field-offset assertions. `borrowed_views` now passes the complete focused
v4 MIR/C/header and GCC output test (`1 passed in 54.19s`), including its
independent Python MIR comparison. A nested `Inner`/`Outer` public-stable
fixture also matches the Python header and confirms padding/offsets
(`1 passed in 41.02s`). The final focused rerun (`1 passed in 54.34s`)
also compiled a separate C translation unit that includes the generated
`borrowed_views` header and calls a mutable-borrow exported function. F6
remains open for explicit manifest header intent,
unknown/private selection rejection, wider public type/layout combinations,
and cross-module ABI probes; this does not authorize inferring exports from
`pub` as the final normal-project interface.

## Finite capability families

`Open` means known missing or incomplete. `Partial` means focused evidence
exists for a subset, not the complete family. `Unverified` means the source
surface exists but there is no sufficient end-to-end SH3 evidence.

| ID | Shared implementation mechanism and remaining dependency | Current evidence/status | Completion evidence before closing row |
| --- | --- | --- | --- |
| F1 | **Canonical type graph.** Reconstruct the exact Alpha.2 `MirType` JSON for builtin, aggregate/stable-ABI structs, copy/owned payload enums, nested `Vec`, decimal, and bounded types from native type/numeric descriptors. Validate child graph, order, identity, source spans, policy, and cycles. Use the same catalog for function return, parameters, locals, instructions, and destructors. | **Partial (uncommitted).** `test_merit_catalog_types_match_python_mir_json` passes against `_descriptor_type_names` and `_numeric_descriptor_type_names` for builtin, nested vector, copy/owned-payload enum, owned-field struct, stable-ABI aggregate, decimal, bounded i64 extremes, and legacy copy-enum/i64-struct names. Cyclic and invalid-decimal catalogs reject. Focused owned-CFG and sourced-contract-local tests pass after numeric threading. The production materializer now uses the catalog for normal locals, contract locals, and return types. Other malformed catalogs, full function/project parity, and all instruction/destructor type use sites remain open. Seven committed-baseline acceptance requests stop at `4129`. | Focused valid/malformed descriptor cases; byte-identical canonical MIR against independent Python materialization for each type family and nested combination; accepted projects advance without type failure; no schema/ABI reinterpretation. |
| F2 | **Canonical function, CFG, and effect assembly.** Preserve block/terminator ordering, placements, source-local IDs, calls, aggregate instructions, contracts, capabilities, explicit ownership effects, return modes, and diagnostics for malformed records. | **Partial (uncommitted).** A focused out-of-order/reachable-block fixture reproduced native status `7`; sorting reachable blocks by ID and pruning reserved joins now matches canonical Python MIR. Reordered placement rows reproduced status `21`; a single materializer-boundary normalization now sorts by block-local ordinal and rejects gaps/duplicates. A malformed terminator in an unreachable block returns status `12` rather than disappearing. The two-record CFG path no longer reads a nonexistent instruction before target validation. Generated-C inspection exposed and fixed an early-return epilogue that dropped the new reachability vector before initialization (native exit `89`). Ownership placement, sourced contract locals, required capability names, and callable ownership metadata pass together (`4 passed in 119.40s`). A type-aware constant writer fixes the observed v4 `i32` JSON-string mismatch; direct MIR cases pass after correcting typed oracle expectations (`5 passed in 183.97s`, then the branch case `1 passed in 17.54s`). All eight fixed-width integer types pass in-range canonical MIR byte comparisons (`8 passed in 245.78s`), including corrected source/spans `i8` evidence (`1 passed in 30.89s`); five overflow/unsigned-negative cases reject (`5 passed in 143.46s`). The shared C integer validator passes its four existing i32/i64 byte-oracle and three invalid-value fixtures (`7 passed in 210.90s`); C emission for other widths is not proved. String constants decode and re-encode canonical JSON; seven escaped/raw UTF-8 cases pass exact MIR bytes, Python C/header comparison, and GCC execution (`1 passed in 35.69s`). Numeric descriptors now reach sourced body/contract literal emission. Four bounded direct cases pass, including the contract-domain exception and a `u64` value above `i64` range (`4 passed in 123.28s`); seven decimal direct cases match the Python materializer or reject excess scale/precision (`7 passed in 198.42s`). Whole-function/project numeric artifact parity and broader malformed-source cases remain open. `ledger_app` committed-baseline status `4107` still needs a fresh native compiler candidate before claiming resolution. | Accepted/rejected CFG and resource-effect differential matrix, including nested match, loop, early return, owned cleanup, contracts/capabilities, and deterministic bytes; `ledger_app` advances or its root mismatch is resolved without relaxing validation. |
| F3 | **Project-wide canonical assembly and destructors.** Collect all source-backed functions, preserve module/visibility identity, reject duplicate/conflicting functions and destructors, normalize payload-free enum storage only at the established representation boundary, and include destructor MIR in the project artifact. | **Open.** The native driver accumulates destructor descriptors but the v4 canonical/C finish path only appends ordinary functions. Python `replacement_project.py` performs duplicate/destructor validation and payload-free storage normalization. | Multi-module and destructor fixtures compare complete MIR/C bytes; duplicate/conflict/missing catalog cases fail closed; ownership lifecycle and native execution match the oracle. |
| F4 | **C type/layout and runtime feature closure.** Emit the oracle's aggregate/enum, stable-layout, numeric, nested vector, filesystem result, string/slice, allocator, and recursive cleanup declarations and helpers in dependency order. Keep semantic ownership separate from C storage strategy. | **Partial (uncommitted aggregate candidate).** The native scalar C spelling table covers all 14 builtin MIR types (`1 passed in 30.46s`). The shared admission rule covers fixed-width integer types without admitting `unit` or unknown builtins (`1 passed in 30.92s`). Catalog-backed aggregate spelling, dependency-ordered integer/bool-field typedefs, nested aggregate declaration order/cycle rejection, and stable `Point` C/header oracle bytes plus GCC execution have focused evidence described above. Construct/load/initializing-store and trivial Copy-field move/drop also have focused evidence, but non-scalar fields, owned/destructor cleanup, enum/numeric graphs, stable public-header layout, and project-level call coverage are open. Aggregate-bearing projects are not accepted yet; the latest first-failure status sweep predates the final edit. | Exact C/header bytes for each type/runtime family, GCC compilation and interpreter/native execution, layout assertions, deterministic order, malformed descriptor rejection. |
| F5 | **C instruction/control/cleanup closure.** Lower every canonical Alpha.2 instruction: constants, copy/move/borrow, construct/load/store, checked/exact numeric and conversion, user/builtin calls, contracts, capability checks, print, drop/deallocate/nop, and return/jump/branch/switch/unreachable. Include filesystem and generic vector operations and destructors. | **Partial (uncommitted).** Native core directly emits const/copy, limited binary/print/call, explicit resource effects, and CFG terminators. A shared C-backend boundary now normalizes dense CFG rows by block and switch ordinal: an interleaved-switch fixture emits byte-identical C (`1 passed in 61.84s`), while all six malformed-switch fixtures preserve their rejection statuses (`6 passed in 178.70s`). Value-mode `ByteSlice` user-call forwarding now passes native MIR/C/header byte comparison to the Python oracle plus GCC runtime execution in the v4 entry test (`1 passed in 33.72s`); this does not prove all call types/modes. Sparse block IDs and the full instruction/call/cleanup surface remain open. Python `_instruction` has the complete dispatch. The candidate acceptance statuses `4492` and `4473` predate these changes. | Table-driven accepted/rejected instruction cases with byte-identical oracle C, side-effect-once and cleanup evidence, native run parity, and deterministic artifacts across the complete accepted corpus. |
| F6 | **Public-header intent and stable ABI.** Select the manifest-requested exported function(s) separately from Merit `pub` visibility; validate unknown/private/unsupported selections; emit ordered stable aggregate layout and borrow ABI declarations. | **Open.** Native backend has a tested per-function header-selection flag, but production still selects all public functions. MPRQ v1 transports the entry **source path**, not header intent; `text_pipeline` stops at `4409`. Python `emit_c_header(..., exported_names=...)` is the oracle. | Explicit native input policy that preserves MPRQ v1 behavior (if a new version is approved, it is additive), selected/unselected and malformed cases, exact compiler/public header bytes, shared-library ABI probes. No host C/header patching or inferred export. |
| F7 | **Versioned artifact authority and host cutover.** The normal project path must consume only the complete native v4 artifact, validate framing/digests/source identity, publish atomically, and never invoke Python snapshot/MIR/C semantics or silently fall back. | **Partial.** v4 framing, digest publication, and import-guard tests exist; `project/replacement.py` still has a legacy snapshot materialization fallback when the native artifact is absent. `prepare_replacement_artifacts` accepts both v3/v4. | Public build/check/shared/run path uses the native artifact only and rejects absent/stale/incompatible responses; import/process guard proves no Python semantic/backend authority; legacy readers remain oracle/compatibility only. |
| F8 | **Compiler project and complete accepted/rejected evidence.** Compile all 45 required compiler modules, ten acceptance applications, and the complete accepted/rejected corpus through the v4 path; compare interpreter/native, protocol, diagnostics, MIR, C, and header bytes without weakening tests. | **Unverified.** The current 45-module v4 executable passes its existing black-box artifact test. All ten acceptance requests finished on the uncommitted F1/F2 candidate, but each stopped at a later backend/header first failure (table above); no complete v4 acceptance, corpus, compiler C/header equivalence, or deterministic repeated build exists. | Finite per-family fixtures, then complete acceptance/corpus differential reports and an uninterrupted compiler-project run with artifact hashes, runtime output, deterministic repeated build, and fail-closed rejected cases. |
| F9 | **SH3 validation and PR handoff.** Confirm the final tree's focused family evidence, affected subsystem gate, clean full gate, hosted authorities, scope/representation audit, and one PR for manual merge review. | **Open.** Older full-gate results predate SH3 changes. No SH3 PR exists. | `SELF_HOSTING.md` per-PR evidence items 1–10, terminal gate markers/results for the final tree, canonical hosted checks, PR link; never auto-merge. SH4–SH6 self-hosting gates are not redefined as SH3 completion. |

## Execution order and boundary rule

1. Finish F1+F2 together as the **canonical representation family**, including
   the current uncommitted type-writer draft and `ledger_app` topology. Use
   focused oracle parity while developing. Do not run a full gate because a
   single project advances to a later status.
2. Complete F3–F5 as coherent backend mechanism families: project/destructor
   assembly, type/runtime layout, then instructions/control/cleanup. Compare
   against the independent Python oracle and native runtime at each capability
   boundary. A family may span several files; commit only when its contract is
   complete and focused evidence passes.
3. Resolve F6's explicit header-intent transport and F7's authority cutover
   without changing existing Alpha.2 language/MIR/ABI behavior or mutating
   MPRQ v1. Record any approved additive request version and its compatibility
   evidence here before using it in production.
4. Close F8 with the complete corpus, all acceptance projects, and compiler
   project. Only then run the affected subsystem and full gates for F9. A
   full gate pass is valid only for the tree it tested. Prepare one SH3 PR and
   stop for manual review.

This matrix is finite by implementation mechanism; any newly exposed failure
must be assigned to an existing family or justified as a genuinely new shared
mechanism here **before** another narrow fix is made.
