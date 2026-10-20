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
at that checkpoint remained open for explicit manifest header intent,
unknown/private selection rejection, wider public type/layout combinations,
and cross-module ABI probes; this does not authorize inferring exports from
`pub` as the final normal-project interface.

MPRQ v2 now adds an opt-in sorted header-export list before source units;
unselected requests remain byte-identical MPRQ v1. The native header finalizer
selects only the named public functions, rejects private/unknown names and
noncanonical names, and leaves canonical MIR/C unchanged. Host framing tests
pass (`10 passed in 0.07s`); the native focused test passes selected, empty,
private, unknown, duplicate, and invalid-name cases (`1 passed in 55.00s`).
The normal artifact-preparation path sends the manifest executable entry as
v2 header intent, records a v2 producer protocol and request digest, and the
native artifact loader verifies that digest; its focused manifest-backed test
passes and the generic stdin adapter executes the resulting binary
(`1 passed in 41.50s`). Public stable-layout combinations beyond the
tested integer/nested aggregate subset, explicit shared-library selection
through the normal CLI, and full project/ABI evidence remain open.

The first two acceptance requests made the remaining F6/F5 coupling visible:
v2 empty-header requests still stopped at `4409` because per-function C
lowering applied public-header type restrictions to every Merit `pub`
function. The driver now passes the explicit selection to that existing C
header flag without changing `pub` in MIR or C symbol identity. The focused
native-entry regression passed (`1 passed in 55.03s`); `text_pipeline` then
advanced to a complete v4 artifact, while `binary_packet` advanced to F5
backend status `4416`. A durable `text_pipeline` oracle/runtime test exposed
and repaired Buffer print lowering. It now passes exact Python C/header
comparison, independent legacy-snapshot canonical MIR bytes, UCRT64 GCC, and
output `Merit Epoch II`, `abc!`, `4`, `327` (`1 passed in 41.52s` on the final
focused tree). This is one project, not full acceptance evidence. The
remaining `binary_packet` `4416` is the shared F5 placement-count boundary,
not another F6 header failure.

The binary-packet legacy snapshots isolate that F5 count: its contract-bearing
function has nine body instructions, four contract instructions, and thirteen
placements. Counting the explicit contract source rows advances its v2 request
to a complete artifact. Independent legacy-snapshot MIR bytes match. Native C
now consumes the existing contract record and local catalogs in placement
order; it emits the source-backed `slice_len` precondition, check, and failure
helper. The focused v4 artifact test passes byte-for-byte C/header comparison
with the Python oracle, GCC compilation, valid runtime output, and rejection
of a short slice. A separate source-backed `requires`/`ensures`/`old()` i64
case includes checked arithmetic and passes C-byte parity and native runtime
output (`1 passed in 59.84s` for the combined focused test). The adjacent v4
framing and contract-catalog regressions pass (`2 passed in 69.39s`). This
closes the represented primitive contract C shapes, not the exact-decimal
arithmetic contracts in the finance projects.

The contract C path is one mechanism, not four independent test failures.
`MirFunctionContractRecord` carries const, binary, check, call, result-capture,
field-load, and old-snapshot instructions; `MirFunctionContractLocal` carries
their declarations. The production driver already had both catalogs for
canonical MIR, but had passed only body, ownership, CFG, and placement catalogs
to the C backend. That mismatch caused it to count contract placements without
emitting their instruction or local rows.
The production C-backend entry now receives those catalogs; its older direct
entry points pass explicit empty catalogs and fail closed if used with placed
contract sources. It does not infer contracts from source text or MIR JSON.
The remaining F5 contract C surface includes declared exact-decimal and
bounded numeric representation, complex field/catalog combinations, and
broader accepted/rejected corpus coverage; unsupported shapes fail closed.

Post-`825a101` read-only MPRQ v2 sweep (empty header selection, saved focused
compiler): `text_pipeline`, `binary_packet`, `generic_result`, `trait_bounds`,
and `borrowed_views` return v4 artifacts (status `0`).
`generic_collections`, `filesystem_capabilities`, and `ledger_app` stop at
C local-type admission (`4410`); `cobol_finance_modernization` stops earlier
at C return/type admission (`4403`). These are first-failure statuses, not
full acceptance passes. Independent legacy snapshots group the unresolved
types rather than the status code: generic collections has nested vectors,
an owned-field struct, and owned-payload enums; filesystem has an owned-payload
file-read result and a Copy-payload file-write result; the two finance
applications have declared decimal/bounded values inside stable aggregates,
with finance modernization also carrying an owned-payload result. Treat
owned-container/layout and declared-numeric/layout as separate F4 families;
do not add a generic `4410` bypass that admits unrepresented C storage.

The owned-container F4 boundary is wider than local admission. Its one
vertical implementation must cover: descriptor-validated owned-field and
owned-payload C type spelling; dependency-ordered typedef collection from
signatures, locals, and nested vector elements; exact Python-oracle typedef
order; value/borrow parameter and local declarations; construction, field/tag
and payload access; explicit move/drop and recursive cleanup of owned fields,
payload variants, and vector elements; and the runtime helpers used by those
operations. `canonical_c_supported_catalog_local_type` currently rejects
the owned-field (`1000000+`) and recursive-owned-payload (`1100000+`) codes,
but admitting the names alone would produce undeclared C types. The current
module finalizer collects only vector, aggregate, and Copy-payload enum codes,
and its vector helper is explicitly limited to Copy elements. The Python
oracle emits owned-field typedefs before aggregate typedefs and recursive
owned-payload typedefs after Copy-payload enums. Keep those ordering and
lifecycle dependencies together; do not let a later `4410` become a false
artifact success. The focused catalog-type oracle baseline is green on the
current committed tree (`1 passed in 34.22s`).
Descriptor-validated owned-field and recursive-owned-enum C type spelling is
now implemented as a private backend helper, with native/interpreter parity
for valid names and missing/duplicate descriptor rejection (`1 passed in
35.73s`). Production local admission remains fail-closed at `4410` until the
corresponding typedef and recursive lifecycle emitters are present; this
intermediate helper does not claim owned-container artifact support.
Private owned-field and recursive-owned-payload typedef emitters now sort
selected descriptor identities, keep owned-field dependencies in declaration
order, and reject missing, duplicate, cyclic, or not-yet-declared children.
Their focused native probe matches the independent Python C emitter's exact
owned-field and tagged-union declaration fragments, and rejects duplicate
descriptors, self-dependent declarations, and `unit`/`void` C fields
(`1 passed in 35.50s`).
At that point, production catalog collection and module integration were
absent, so no acceptance status was promoted.
The existing driver collects vector, aggregate, and Copy-enum roots separately
from function records. Its aggregate collector follows only aggregate children.
A private owned-type collector now walks reachable descriptor children from
return/parameter/local roots, deduplicates nested owned-field and owned-enum
identities, and rejects missing catalog rows; a direct native/interpreter probe
for an owned-enum-to-owned-field path passed (`1 passed in 34.11s`). The
production driver now accumulates the owned roots, and the finalizer has an
owned-aware path that inserts field typedefs before general aggregates and recursive-enum
typedefs after Copy enums. A focused native/interpreter probe extracted its
generated C and GCC accepted the declaration order (`1 passed in 37.24s`).
Owned local admission and recursive cleanup remain closed; this is declaration
integration evidence, not an accepted-project result. The existing Copy-vector
finalizer regression also remains green after the owned-aware signature change
(`1 passed in 34.04s`).
The graph collector also adds nested vector/aggregate/Copy-enum identities to
their existing production catalogs. The focused `Vec` → owned enum → owned
field path, including missing-descriptor rejection, passed interpreter/native
parity (`1 passed in 34.87s`). Owned-element vector runtime and recursive
cleanup remain necessary before broad local admission.
The first private recursive cleanup emitter now follows owned-field children
and payload-enum tags without changing MIR ownership effects. Its emitted
statements match the independent Python oracle exactly for an enum → owned
field → Buffer graph, with interpreter/native parity and self-cycle rejection
(`1 passed in 35.02s`). At that point it was not yet connected to resource-
effect lowering; owned-element vector runtime remains unavailable.
The explicit MIR resource-effect emitter now delegates owned-field and
recursive-enum drops to that helper while retaining move assignment and the
existing effect/operand checks. An owned move/drop probe matches Python-oracle
C lines with interpreter/native parity (`1 passed in 36.34s`); one existing
Buffer move/drop regression remains green (`1 passed in 33.60s`). This does
not open owned local admission or cover replacement cleanup placements yet.
The vector runtime emitter now has a separately selected owned-element path:
`Vec<Buffer>` runtime bytes match the Python oracle and a GCC lifecycle driver
observes replace/pop/drop cleanup exactly once (`1 passed in 34.89s`). The
module finalizer selects this path and its generated C compiles/executes
(`1 passed in 35.18s`). The Copy-only helper still matches oracle bytes and
still rejects owned elements (`2 passed in 67.48s`). Nested owned vector type
mangling, local admission, and production placement cleanup remain open.
The call lowerer now emits typed owned-element `push`, `pop`, and `replace`
calls and rejects owned `get`/`set` instead of copying or discarding resources.
A direct MIR-record probe matched the expected C call lines with
interpreter/native parity and rejected owned `get` and `set`
(`1 passed in 34.36s`);
the pre-existing Copy-vector operation oracle remained byte-identical
(`1 passed in 36.40s`). This is not yet an end-to-end owned vector project
build: effect-catalog association, `vec_transfer`, nested owned vector names,
and owned local/placement closure still need evidence.
The catalog-backed vector name now recursively mangles owned-field and
recursive-owned-enum element graphs, including ordered payload variants; a
focused native/interpreter probe matched the Python oracle's vector names and
complete runtime-helper bytes and rejected a cyclic descriptor
(`1 passed in 34.54s`). The earlier primitive/nested-Vec name regression stayed
green (`1 passed in 33.59s`). The module finalizer now orders vector runtimes by
depth, then mangle, as the oracle does; a reverse-catalog `Vec<Vec<i64>>` probe
matched the full runtime-helper block and produced GCC-executable C
(`1 passed in 36.02s`). General aggregate/Copy-enum element mangles and owned
project admission remain open.
The owned-aware module probe now includes a vector of owned-field structs in
addition to its tagged enum. Its vector helper block matches the Python
oracle, the declaration order is stable, and GCC accepts the assembled C
(`1 passed in 35.23s`). This validates the private F4 runtime/layout path but
does not open F5 project-level ownership-call or cleanup placement coverage.
The final-tree focused owned-call and Copy-call regressions passed together
(`2 passed in 69.86s`) before the F4 runtime/layout checkpoint.
An F5 owned-constructor extension validates owned-field and recursive-payload
enum descriptors, admits their catalog-backed local types only with resource
effects, and zero-initializes those C locals as aggregates. The descriptor
probe passes interpreter/native parity, including missing-field and
out-of-range variant rejection (`1 passed in 36.90s`). An owned-field
constructor/drop and a nested recursive-enum constructor/drop each emitted a
complete C module byte-identical to the Python oracle and compiled with GCC
(`1 passed in 20.95s`, `1 passed in 34.80s`). Missing descriptor/effect
catalogs reject before C emission (`2 passed in 68.17s`).
Value-mode owned-field and recursive-owned-enum parameters/returns now use the
existing one-block placed-move proof and the descriptor-validated C type
catalog. A field value ABI probe exposed missing transitive Buffer runtime
selection when Buffer was present only inside an owned type; the module
finalizer now derives Buffer/text/slice needs from reached owned descriptors.
The field and enum return modules match Python-oracle C bytes and execute
through separate GCC callers (`1 passed in 35.37s`, `1 passed in 34.55s`).
Missing move, public owned return, borrowed owned parameter, and borrowed
owned return reject with their bounded statuses (`4 passed in 135.69s`).
Borrowed owned-aggregate ABI, multi-block transfer, field/payload extraction,
and whole-project acceptance remain open. This is not project-level F5 closure.
The next bounded read-only borrowed path admits private shared/mutable borrowed
owned-aggregate parameters and validates recursive owned-enum tag loads against
the descriptor catalog. Both parameter modes emit complete C byte-identical
to the Python oracle and run through a GCC caller that retains and drops the
original owned payload (`2 passed in 55.50s`). A borrowed payload-copy record
still rejects before C emission (`1 passed in 39.55s`). Owned payload/field
extraction and borrowed return/call forwarding remain unproved; this read-only
tag path is not a blanket authorization to copy owned resources.
The native C comparison validator now accepts the complete eight-type
fixed-width integer family already present in canonical MIR and the Python
oracle. Six newly admitted i8/i16/u8/u16/u32/u64 equality fixtures matched
complete oracle C/header bytes and compiled/executed with GCC
(`6 passed in 212.16s`); the existing i32/i64 comparison fixtures cover the
other relational symbols and reran on this candidate with GCC execution
(`7 passed in 241.92s`). Checked i8/u8 arithmetic, which previously risked
emitting an i64 helper into a narrow result, now rejects before C emission
(`2 passed in 68.13s`) until the shared checked-helper family is ported.
Full checked fixed-width arithmetic remains an explicit F5 dependency.
The checked-arithmetic F5 slice now emits the oracle's complete eight-width
`+`, `-`, `*`, and `/` helper family through one canonical C path. The direct
32-helper byte-oracle/GCC compilation case passed (`1 passed in 35.74s`),
six representative new-width full-C/header oracle cases passed and compiled
(`6 passed in 191.99s`), and all eight existing i32/i64 full-C/header cases
passed on the candidate (`8 passed in 258.80s`). The i8/u8 native generated-C
runtime and overflow-exit cases passed (`2 passed in 69.82s`); a mixed-width,
out-of-order feature request emits helpers in oracle order (`1 passed in
34.36s`). The earlier narrow-type rejection evidence above is historical and
has been superseded. Existing boolean-arithmetic rejection remains in place.
This closes the checked fixed-width helper mechanism, not F5's other numeric,
instruction, control, or cleanup dependencies. The complete 32-case
full-module cross-product and subsystem/full gates remain deferred to the
appropriate larger validation boundary.
The next F4 declared-numeric candidate is deliberately private: after the
canonical MIR descriptor validator accepts a decimal or bounded descriptor,
it selects oracle-compatible C storage (`int64_t` through precision 18,
`__int128` above it, or the bounded base integer type). A focused probe passes
interpreter/native parity for decimal precisions 18/19 and bounded `u64`, and
rejects absent/duplicate descriptors without writing C (`1 passed in
34.28s`). This is **not** production numeric admission: exact range/rounding
helpers, arithmetic, print, aggregate layout, and project artifact parity
remain grouped F4/F5 dependencies before those types may reach emitted C.
The same private candidate now emits oracle-byte-identical bounded `u64`/`i64`
range checkers from validated two-limb bounds, compiles and executes their
boundary cases, and traps an out-of-range `u64` value (`1 passed in 34.21s`).
Its decimal checkers plus shared rounding helper match oracle bytes for
18/19-digit descriptors, compile and execute boundary values, and trap decimal
overflow (`1 passed in 34.35s`). Production numeric type admission,
instruction lowering, exact print, aggregate layout, and complete acceptance
parity remain open; the checker probes alone do not close that family.
The numeric catalog now reaches the same native module finalizer used by the
v4 project driver. That finisher validates and deduplicates numeric roots,
sorts decimal helpers before bounded helpers as the oracle does, includes the
required C prelude, and rejects duplicate requested codes; the collector-to-
finalizer probe matches oracle helper bytes and GCC-compiles (`1 passed in
35.21s`). The existing nonnumeric v4 artifact baseline still passes on this
tree (`1 passed in 33.70s`). At that checkpoint, numeric return/local/parameter admission and
instruction lowering remained fail-closed, so no finance acceptance or SH3
production numeric closure is claimed yet.

The next F4/F5 scalar-numeric boundary threads the validated numeric catalog
through the common function backend. Decimal and bounded parameters, returns,
locals, constants, arithmetic, comparisons, and printing now use the same
descriptor-backed C type and helper path as the module finalizer. Focused
native/Python C-byte parity and GCC execution passed for decimal and bounded
parameter/return functions (`2 passed in 69.74s`), direct typed literal and
range rejection (`1 passed in 34.53s`), all four arithmetic operations and
printing as oracle fragments (`1 passed in 36.53s`), and complete emitted-C
decimal/bounded addition functions (`2 passed in 71.25s`). The nonnumeric v4
artifact baseline remained byte-identical (`1 passed in 34.46s`). The
bounded-only emitted-C test also exposed a Python-oracle prelude defect:
`merit_exact_numeric_failure` uses `fprintf`, but `<stdio.h>` was absent when
no decimal or other stdio feature was present. The oracle prelude now includes
it for either declared-numeric family, and the bounded-only C compiles. This
does **not** close F4/F5: aggregate numeric fields/layout, public headers,
whole-project acceptance, and broader numeric instruction combinations remain
open.

The aggregate-numeric F4 follow-on now discovers decimal/bounded leaves from
reachable aggregate descriptors, deduplicates them across functions, and emits
their validated C field storage through the shared aggregate typedef path.
The direct two-field decimal/bounded probe rejects a missing numeric catalog
and GCC-compiles the emitted typedef (`1 passed in 36.82s`); the preexisting
aggregate dependency-order regression also passed. A complete module whose
only decimal use is an aggregate field matches the Python oracle byte for byte
and executes under GCC (`1 passed in 36.05s`). These tests do not yet prove
numeric-field construct/load/store, aggregate call modes, stable public-header
layout, or finance-project acceptance. F4 therefore remains partial.
The existing nonnumeric v4 artifact baseline remains byte-identical after
the shared finalizer change (`1 passed in 34.58s`).
The same numeric-field catalog now passes complete native/Python C-byte and
GCC execution checks for construction (`1 passed in 37.09s`) and field load
plus initializing store (`2 passed in 71.83s`), with returned decimal storage
checked at runtime. The backend still rejects replacement stores that would
require cleanup. Aggregate parameter/return call modes and stable public
headers remain separate F5/F6 work; this is not whole-project F4 closure.
The seven-test numeric-aggregate boundary, including the old aggregate-order
and v4 artifact baselines, passed together in 179.20s before check-in.
After that check-in, a focused numeric-aggregate **by-value** parameter and
return case matched the complete Python C artifact and executed under GCC
(`1 passed in 35.60s`). Borrowed/mutable-borrow signatures and user-call
arguments still pass through the older integer/bool-only aggregate field-count
gate. Those checks form one descriptor-aware F5 mechanism rather than separate
per-project exceptions; value-mode evidence does not close that mechanism.
The descriptor-aware Copy aggregate field count now reaches native signature,
borrowed-local, return, call-result, and callable-parameter checks without
changing ownership modes. By-value, borrowed, and mutable-borrowed
numeric-bearing aggregate signatures match complete Python C bytes and pass
GCC execution. The focused signature/call-regression boundary passed 11 tests
in 361.78s, including existing scalar-call rejection coverage. This does not
yet prove an actual multi-function user-call artifact with a numeric-bearing
aggregate argument; F5 remains partial until that and the broader acceptance
matrix are exercised.
That exact F5 user-call artifact now passes for value, borrowed, and mutable-
borrowed aggregate arguments/results: native complete C bytes equal the Python
oracle and each generated C program runs under GCC (`1 passed in 22.57s`,
`2 passed in 74.56s`). Two borrowed-argument mode mismatches reject without
silently changing a borrow into a value call (`2 passed in 74.14s`). Wider
multi-module ownership/call combinations, numeric direct-call variants, and
acceptance projects remain open.
The six-test accepted/rejected numeric-aggregate user-call boundary, including
the old scalar borrowed-parameter rejection, passed together in 128.38s
before check-in.

The next F3 candidate adds native validation of contiguous destructor body,
CFG, and placement sections, duplicate targets, positive target codes, and
unclaimed rows before project assembly. The focused valid/malformed catalog
regression passes in interpreter and native execution (`1 passed in 40.71s`).
The destructor-bearing v4 artifact regression still fails at the absent
canonical `destructors` entry. This closes only the fail-closed descriptor
subfamily, not F3 MIR/C/header/runtime equivalence.
The native canonical writer now consumes a validated destructor's body, CFG,
and placement slice through the shared sourced-CFG materializer. It preserves
the declared target and mutable-borrow `self` local, and the project assembly
helper places destructor entries before functions in canonical key order.
The focused interpreter/native probe checks byte-identical canonical MIR and
project assembly (`1 passed in 34.31s`). This is MIR-writer evidence only:
the production driver does not yet publish destructor entries, and native C
emission, recursive cleanup, and complete artifact parity remain open.
The C-backend audit found the concrete remaining seam: the shared CFG
instruction emitter in `canonical_c_append_function_core_ordered` assumes a
function prototype, ordinary `bN` labels, and an ordinary return. The Python
oracle instead uses a target-pointer destructor signature, initializes `m0`
from `*self`, uses `b_destructor_N` labels, and writes `m0` back on return.
The existing shared instruction and CFG validation logic should remain the
single C path; a bounded destructor mode must change those emission boundaries
without duplicating instruction semantics. Destructor prototypes must precede
bodies and both must precede ordinary function bodies in the final module.
The current bounded candidate connects each validated destructor descriptor to
both native MIR and C writers in the production driver. Focused legacy
one-field and general two-field `Marker` requests now produce complete native
MIR, C, and header bytes matching the Python oracle; the generated C compiles
and direct destructor calls print the expected output (`2 passed in 76.33s`).
The catalog-backed aggregate destructor also matches the oracle's standalone C
prototype/body, and the ordinary v4 baseline still passes (both rerun together:
`2 passed in 72.08s`). The shared CFG
materializer accepts the destructor's implicit unit return without relaxing
ordinary function validation.

This is **partial lifecycle progress, not F3 closure**. The original ordinary
C backend status `4515` (4400 + resource-effect status 115) is resolved for a
validated legacy one-field destructor catalog: implicit cleanup and explicit
`drop(marker)` each produce exactly one destructor call and byte-identical
Python-oracle MIR/C/header artifacts. The focused artifact/writer/non-destructor
boundary passed (`6 passed in 216.90s`) before an additional control-flow
probe; existing owned/vector resource-effect oracle tests still pass
(`2 passed in 71.41s`). Early return with a live `Marker` and ordinary
`if (1 == 1)` condition passes both bundle and artifact paths, exact Python
MIR/C/header byte comparison, and native execution with one destructor print
(`2 passed in 36.63s`). The earlier `if (true)` probe stopped at native driver
status `4368`; temporary status-range discrimination traced it through
assembly/semantic/body lowering to `sfr_expression_unknown_failure_status`.
The independent reference project checker rejects that source as
`M3003: unknown variable true`: Alpha.2 has no `true` keyword literal, so the
probe was invalid, not an early-return cleanup defect or a new syntax request.
Two-field scalar aggregate targets with a source destructor now also pass
complete MIR/C/header oracle parity, native execution, and exactly-once
implicit/explicit cleanup (`1 passed in 50.72s`, `1 passed in 37.09s`). The
aggregate's destructor policy is validated separately from Copy field count;
the complete destructor/resource boundary suite passes on the candidate tree
(`12 passed in 204.18s`). Nontrivial nested fields still fail closed. Recursive cleanup of owned
aggregate fields and move/replace lifecycle remain open.
Black-box rejected source requests now cover duplicate and unknown destructor
targets: the first fails at the source struct catalog (`971`), the second at
destructor target resolution (`992`), with no accepted artifact (`2 passed in
36.78s`). The existing descriptor-section test covers malformed spans,
ordering, duplicate target codes, and invalid type codes separately.
A two-module imported-function/struct/destructor request now matches independent
Python project-assembly MIR bytes, C/header bytes, and runtime cleanup. The
native recursive resource writer also preserves exact cleanup for an owned
custom-destructor child in a one-field owned struct and a two-field aggregate,
including explicit drop and outer-before-inner custom-destructor order (`5
passed in 128.83s`). The direct scalar-field and multi-module tests do not yet
cover arbitrary project ordering, vector/enum-nested resources, move/replace,
or cross-module conflicting destructor declarations.

The next F5 call-result probe found an older hardcoded admission subset in the
native C backend. It rejected an otherwise descriptor-valid owned struct result
at driver status `4461`. Call-result admission now uses the same complete
catalog-backed type validator as local declarations, with `unit` explicitly
retained as a result-less call type; existing result mode and callee/result
identity checks remain intact. An owned-struct destructor result and a Copy
payload-enum result match independent Python MIR/C/header bytes and execute
with expected cleanup/output. The existing black-box v4 artifact test also
passes on the final tree (`3 passed in 103.14s`). This is a bounded call-result
subset, **not** F5 closure. A fresh read-only request sweep with empty
public-header selection returns v4 for `text_pipeline`, advances
`generic_collections` from `4461` to backend status `4412`,
`filesystem_capabilities` from `4461` to `4465`, and `ledger_app` from `4461`
to `4493`. These next boundaries require separate diagnosis and coverage.
The `generic_collections` `4412` root was isolated with temporary return-site
instrumentation, then restored: local C type spelling rejects vector code
`1500002`, whose descriptor child is aggregate `1200001` (`Pair<i64,i32>`).
`canonical_c_append_catalog_type_mangle` has no aggregate branch and lacks the
source buffer needed for the aggregate's span-derived ABI identity. This is an
F4 vector/aggregate name-transport dependency, not an ownership-metadata or
recursive-enum defect. Preserve the existing fail-closed result until native
source-aware vector naming matches the Python MIR/C mangle and runtime helpers.

The source-aware F4/F5 candidate now carries aggregate identity through vector
type mangling, local/call/resource spelling, and runtime emission. It also
admits descriptor-validated Copy aggregate vector elements, the existing
owned-field and recursive-enum payload loads, and the existing owned-vector
transfer call. The `generic_collections` request now returns a complete v4
artifact; its native C/header bytes equal the independent Python emitter for
the native MIR, the C compiles, and its executable output equals the reference
project build (`1 passed in 20.06s`). This closes the observed vector/aggregate
name-transport slice, **not** all F4/F5 coverage or native-versus-Python MIR
materialization. A read-only request sweep on this candidate returns v4 for
`text_pipeline`, `binary_packet`, `generic_result`, `trait_bounds`,
`generic_collections`, and `borrowed_views`; the first remaining project
statuses are `bootstrap_lexer` 4486, `cobol_finance_modernization` 4534,
`filesystem_capabilities` 4465, and `ledger_app` 4493. These statuses need
root-cause grouping before the next implementation family.

The next F4/F5 enum-CFG candidate isolates `ledger_app` `4493`: the Python
materializer switches directly on nested payload-free `LedgerError` (Copy-enum
identity 0), and the Python C emitter reads its `.tag`; the native backend had
required an `i64` switch local. A minimal nested-enum source reproduced `4493`.
Native switch validation/emission now admits descriptor-valid Copy and recursive
owned enum subjects, including the established payload-free Copy-enum storage,
and emits the tag access. This exposed module status `4534` for an outer Copy
enum containing an inner Copy enum; the typedef emitter now accepts only an
already-emitted inner Copy enum, retaining fail-closed ordering. The focused
nested match matches native/Python C and header bytes, GCC-compiles, and runs
with the expected output (`1 passed in 33.81s`). `ledger_app` advances to
module status `4515`; `cobol_finance_modernization` remains at module `4534`,
while the unrelated bootstrap and filesystem first statuses remain `4486` and
`4465`. These are not yet whole-project acceptance or F4/F5 closure.

### Numeric aggregate cleanup and contract boundary (Windows candidate)

The native C backend now threads the validated numeric catalog through recursive
aggregate/vector cleanup. Declared-numeric Copy leaves emit the same explicit
no-op cleanup as the Python oracle. Contract emission reuses the existing
declared-numeric literal and checked-arithmetic writers, admits validated
numeric aggregate field loads, and preserves the established rule that a
bounded comparison constant may lie outside the bounded value's domain.
One focused v4 fixture covers decimal and bounded fields, explicit aggregate
drop, decimal pre/postconditions, an out-of-domain bounded precondition,
exact Python-oracle C/header bytes, GCC linking, and native execution
(`1 passed in 34.30s` on the latest tree). Four adjacent numeric/contract
test selections passed seven parameterized cases in 267.85s on the final
candidate tree. This is focused evidence, not a subsystem or full gate.
On the latest built candidate, `ledger_app` advanced from `4515` through
`4534` to `4465`; `cobol_finance_modernization` moved from `4534` to `4510`.
Both are first-failure diagnostics, **not** acceptance passes. The remaining
statuses are separate mechanisms and do not close F4/F5.

### Multi-block owned-result and aggregate-payload boundary (Windows candidate)

The first `cobol_finance_modernization` backend failure, `4510`, was the
single-block owned-return guard. Its nine reachable return blocks construct
fresh owned `TransferResult` values; canonical MIR has no separate move
instruction for those returns. The backend now requires each reachable owned
return to have either one placed move or a same-block, same-type enum
constructor, while retaining fail-closed rejection for unproved producers.
The next failure, `4553`, was a recursive owned-enum typedef guard that
mistook an already-emitted aggregate payload for another owned enum. The
production writer now requires that aggregate payload to be present in the
aggregate catalog emitted earlier. A focused two-branch aggregate-payload
fixture and the complete COBOL finance project pass exact native-versus-Python
canonical MIR, C, and selected-header bytes, GCC compilation, and native
output equality with the reference project build (`1 passed in 37.92s`).
The final-tree finance fixture plus adjacent owned-enum and rejected-transfer
selection passed seven cases in 255.82s. A contradictory borrowed parameter
with an owned move now fails closed with the established status `9`.
This is one acceptance project through v4, **not** F4/F5/F8 closure or a
full/subsystem gate. Direct owned-parameter returns with branch-scoped
`nested_transfer` effects remain a distinct represented shape to audit;
the current producer check still fails closed for that shape.

The post-commit `8f516ee` v4 request sweep completed all ten acceptance
requests. Seven return a complete artifact: `binary_packet`,
`borrowed_views`, `cobol_finance_modernization`, `generic_collections`,
`generic_result`, `text_pipeline`, and `trait_bounds`. The first remaining
statuses are `bootstrap_lexer` `4486`, `filesystem_capabilities` `4465`, and
`ledger_app` `4465`. The extra `result_app` example stops at `4502` and is
not counted among the ten acceptance applications. Only COBOL finance has
the full project MIR/C/header/runtime differential evidence recorded above;
the other six successful responses still need complete F8 comparison.

### Filesystem calls, resource placement, and numeric enum payload boundary

The `4465` first failure shared by `filesystem_capabilities` and `ledger_app`
is the native C writer's fail-closed unknown-builtin path for `file_read` and
`file_write`, not two unrelated project defects. Treat them as one F4/F5
capability family. The Python oracle selects the result type from the call's
resolved local, emits a type-mangled helper call, requires `FileReadResult`
storage to be a recursive owned enum with `Buffer` and `i64` payloads, and
requires `FileWriteResult` storage to be a copy-payload enum. Its module
prelude conditionally adds `errno.h` and `sys/stat.h`; its runtime emits the
filesystem error mapper, directory probe, and type-specific read/write
helpers after function prototypes and before checked/numeric/vector helpers.
The native writer must preserve that exact ordering and use the resolved MIR
argument modes when passing the `Buffer` pointer to `file_write`.

The native writer now selects result-specific helpers from explicit call
features, validates the two operand types and resolved result storage, and
emits the oracle's conditional includes, helpers, and separator ordering.
Copy-payload enum mangling and numeric payload typedefs use the canonical
catalog. The ledger request exposed two independent later first failures:
the backend incorrectly equated an ownership producer instruction ID with a
contract-shifted global placement ID (`4511`), and the copy-enum typedef
writer lacked numeric descriptors for `LedgerResult(USD)` (`4534`). Both are
corrected without changing canonical MIR or Alpha.2 behavior. The focused
two-project test compares complete native/Python canonical MIR, C, and selected
header bytes, compiles the native C with GCC, and compares stdout and written
file bytes with independent reference builds (`2 passed in 40.83s`). Two
malformed source calls (wrong read result type and wrong write payload type)
reject in native artifact mode; the four-case accepted/rejected file passes
(`4 passed in 39.64s`). The adjacent call/owned-result suite passes (`5 passed
in 82.41s`), and destructor/cleanup artifacts pass (`15 passed in 501.28s`).
The legacy bundle endpoint is intentionally only a record producer and need
not reject these malformed calls before native backend validation. This
evidence closes the filesystem/numeric-copy-enum/contract-shifted-placement
mechanism for the two affected acceptance projects; it does not close all
F4/F5/F8 surfaces or justify a full gate yet.

### Alpha.2 integer branch condition (focused CFG boundary)

The earlier `bootstrap_lexer` first failure `4486` mapped to the native C
writer's bool-only CFG branch guard. The reference checker accepts a direct
`i32` condition, while canonical Python MIR-to-C emits a C branch for the
resolved operand without changing its type. The native guard now admits only
the existing `bool` and Alpha.2 `i32` representations; the invalid `i64`
condition remains rejected. A source-backed i32 branch produces parseable
native MIR with an i32 branch local, byte-identical Python-oracle C/header,
GCC compilation, and expected runtime output. The
new fixture plus the existing boolean-branch and malformed-CFG cases pass
(`8 passed in 272.26s`). This proves the focused condition family, not that
the 45-module compiler project advances past its next failure.

A read-only legacy snapshot probe of the full compiler project ran longer
than seven minutes and ended at status `4861` without a decodable bundle;
that result cannot identify the original branch's function or prove v4
compiler-project completion. Do not repeat that long diagnostic automatically.

### Nine-project full artifact differential boundary

The focused acceptance-artifact fixture now builds one native v4 compiler and
one legacy snapshot producer, then checks every required acceptance project
except `bootstrap_lexer`. For each of the nine, native canonical MIR bytes
equal independently materialized Python-oracle MIR; native C and selected
header bytes equal the Python MIR-to-C emitter; GCC compiles the native C;
and the native executable's stdout matches the reference project build.
`filesystem_capabilities` and `ledger_app` also match their reference-written
file bytes in isolated directories. The two malformed filesystem calls still
reject in native artifact mode (`11 passed in 46.36s`). This supersedes the
earlier seven-of-ten request-status sweep: nine of ten acceptance projects
now have full focused artifact/runtime parity, while `bootstrap_lexer` has
neither a complete v4 artifact nor this evidence. F8 still requires the
45-module compiler project, accepted/rejected corpus, protocol/diagnostic
coverage, and deterministic repeated-build proof.

## Finite capability families

`Open` means known missing or incomplete. `Partial` means focused evidence
exists for a subset, not the complete family. `Unverified` means the source
surface exists but there is no sufficient end-to-end SH3 evidence.

| ID | Shared implementation mechanism and remaining dependency | Current evidence/status | Completion evidence before closing row |
| --- | --- | --- | --- |
| F1 | **Canonical type graph.** Reconstruct the exact Alpha.2 `MirType` JSON for builtin, aggregate/stable-ABI structs, copy/owned payload enums, nested `Vec`, decimal, and bounded types from native type/numeric descriptors. Validate child graph, order, identity, source spans, policy, and cycles. Use the same catalog for function return, parameters, locals, instructions, and destructors. | **Partial (uncommitted).** `test_merit_catalog_types_match_python_mir_json` passes against `_descriptor_type_names` and `_numeric_descriptor_type_names` for builtin, nested vector, copy/owned-payload enum, owned-field struct, stable-ABI aggregate, decimal, bounded i64 extremes, and legacy copy-enum/i64-struct names. Cyclic and invalid-decimal catalogs reject. Focused owned-CFG and sourced-contract-local tests pass after numeric threading. The production materializer now uses the catalog for normal locals, contract locals, and return types. Other malformed catalogs, full function/project parity, and all instruction/destructor type use sites remain open. Seven committed-baseline acceptance requests stop at `4129`. | Focused valid/malformed descriptor cases; byte-identical canonical MIR against independent Python materialization for each type family and nested combination; accepted projects advance without type failure; no schema/ABI reinterpretation. |
| F2 | **Canonical function, CFG, and effect assembly.** Preserve block/terminator ordering, placements, source-local IDs, calls, aggregate instructions, contracts, capabilities, explicit ownership effects, return modes, and diagnostics for malformed records. | **Partial (uncommitted).** A focused out-of-order/reachable-block fixture reproduced native status `7`; sorting reachable blocks by ID and pruning reserved joins now matches canonical Python MIR. Reordered placement rows reproduced status `21`; a single materializer-boundary normalization now sorts by block-local ordinal and rejects gaps/duplicates. A malformed terminator in an unreachable block returns status `12` rather than disappearing. The two-record CFG path no longer reads a nonexistent instruction before target validation. Generated-C inspection exposed and fixed an early-return epilogue that dropped the new reachability vector before initialization (native exit `89`). Ownership placement, sourced contract locals, required capability names, and callable ownership metadata pass together (`4 passed in 119.40s`). A type-aware constant writer fixes the observed v4 `i32` JSON-string mismatch; direct MIR cases pass after correcting typed oracle expectations (`5 passed in 183.97s`, then the branch case `1 passed in 17.54s`). All eight fixed-width integer types pass in-range canonical MIR byte comparisons (`8 passed in 245.78s`), including corrected source/spans `i8` evidence (`1 passed in 30.89s`); five overflow/unsigned-negative cases reject (`5 passed in 143.46s`). The shared C integer validator passes its four existing i32/i64 byte-oracle and three invalid-value fixtures (`7 passed in 210.90s`); C emission for other widths is not proved. String constants decode and re-encode canonical JSON; seven escaped/raw UTF-8 cases pass exact MIR bytes, Python C/header comparison, and GCC execution (`1 passed in 35.69s`). Numeric descriptors now reach sourced body/contract literal emission. Four bounded direct cases pass, including the contract-domain exception and a `u64` value above `i64` range (`4 passed in 123.28s`); seven decimal direct cases match the Python materializer or reject excess scale/precision (`7 passed in 198.42s`). Whole-function/project numeric artifact parity and broader malformed-source cases remain open. `ledger_app` committed-baseline status `4107` still needs a fresh native compiler candidate before claiming resolution. | Accepted/rejected CFG and resource-effect differential matrix, including nested match, loop, early return, owned cleanup, contracts/capabilities, and deterministic bytes; `ledger_app` advances or its root mismatch is resolved without relaxing validation. |
| F3 | **Project-wide canonical assembly and destructors.** Collect all source-backed functions, preserve module/visibility identity, reject duplicate/conflicting functions and destructors, normalize payload-free enum storage only at the established representation boundary, and include destructor MIR in the project artifact. | **Partial.** Production v4 artifacts include validated source-defined destructor MIR and C; direct scalar one-/two-field, one imported-module, and owned-child one-/two-field fixtures match Python MIR/C/header bytes and native execution. Automatic/explicit drops and outer-before-inner callback order execute once; comparison-guarded early return also has parity. Duplicate and unknown source targets reject (`971`, `992`), complementing malformed descriptor-section coverage. The `if (true)` probe was invalid Alpha.2 source (reference `M3003`). Wider nested resource kinds, move/replace, general multi-module ordering, and cross-module conflicting destructor coverage remain open. | A destructor-bearing fixture must compare complete native/Python MIR, C, and header bytes and execute automatic cleanup with no double destruction. Duplicate/conflicting and malformed destructor catalogs must fail closed. Multi-module ordering, payload-free enum storage, and ownership lifecycle must match the oracle. |
| F4 | **C type/layout and runtime feature closure.** Emit the oracle's aggregate/enum, stable-layout, numeric, nested vector, filesystem result, string/slice, allocator, and recursive cleanup declarations and helpers in dependency order. Keep semantic ownership separate from C storage strategy. | **Partial (uncommitted aggregate candidate).** The native scalar C spelling table covers all 14 builtin MIR types (`1 passed in 30.46s`). The shared admission rule covers fixed-width integer types without admitting `unit` or unknown builtins (`1 passed in 30.92s`). Catalog-backed aggregate spelling, dependency-ordered integer/bool-field typedefs, nested aggregate declaration order/cycle rejection, and stable `Point` C/header oracle bytes plus GCC execution have focused evidence described above. Construct/load/initializing-store and trivial Copy-field move/drop also have focused evidence, but non-scalar fields, owned/destructor cleanup, enum/numeric graphs, stable public-header layout, and project-level call coverage are open. Aggregate-bearing projects are not accepted yet; the latest first-failure status sweep predates the final edit. | Exact C/header bytes for each type/runtime family, GCC compilation and interpreter/native execution, layout assertions, deterministic order, malformed descriptor rejection. |
| F5 | **C instruction/control/cleanup closure.** Lower every canonical Alpha.2 instruction: constants, copy/move/borrow, construct/load/store, checked/exact numeric and conversion, user/builtin calls, contracts, capability checks, print, drop/deallocate/nop, and return/jump/branch/switch/unreachable. Include filesystem and generic vector operations and destructors. | **Partial.** Native core directly emits const/copy, limited binary/print/call, explicit resource effects, and CFG terminators. A shared C-backend boundary now normalizes dense CFG rows by block and switch ordinal: an interleaved-switch fixture emits byte-identical C (`1 passed in 61.84s`), while all six malformed-switch fixtures preserve their rejection statuses (`6 passed in 178.70s`). Value-mode `ByteSlice` user-call forwarding passes native MIR/C/header byte comparison to the Python oracle plus GCC runtime execution (`1 passed in 33.72s`). The complete eight-width checked `+`, `-`, `*`, `/` helper mechanism now passes direct 32-helper oracle/GCC evidence, sampled new-width full-module oracle/C compilation, all eight old-width full-module cases, narrow runtime/overflow traps, and mixed-feature deterministic order (details above). The full 32-case module cross-product, sparse block IDs, and other instruction/call/cleanup surfaces remain open. Python `_instruction` has the complete dispatch. The candidate acceptance statuses `4492` and `4473` predate these changes. | Table-driven accepted/rejected instruction cases with byte-identical oracle C, side-effect-once and cleanup evidence, native run parity, and deterministic artifacts across the complete accepted corpus. |
| F6 | **Public-header intent and stable ABI.** Select the manifest-requested exported function(s) separately from Merit `pub` visibility; validate unknown/private/unsupported selections; emit ordered stable aggregate layout and borrow ABI declarations. | **Partial.** Additive MPRQ v2 carries explicit sorted header exports while v1 remains unchanged; native header selection, empty selection, private/unknown and malformed-name rejection pass focused tests. Manifest executable entry flows through preparation and versioned digest validation. Stable nested aggregate and borrowed-view headers match the Python oracle, and a separate C consumer compiles. Shared-library CLI selection, wider public layout/type combinations, all affected acceptance projects, and full ABI evidence are not yet proved. | Explicit native input policy that preserves MPRQ v1 behavior (if a new version is approved, it is additive), selected/unselected and malformed cases, exact compiler/public header bytes, shared-library ABI probes. No host C/header patching or inferred export. |
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
