# Merit v0.1.0-alpha.2 Closure Matrix

## Objective

`v0.1.0-alpha.2` removes Python semantic authority from normal production compilation for the complete documented alpha.1 language surface.

Python remains the independent reference/oracle until trust qualification.

This file is the authoritative work queue for alpha.2 closure.

A feature is not "closed" because isolated parser/HIR/MIR tests exist. Closure means the supported source construct travels through the production replacement path and satisfies the evidence requirements below.

## Production replacement path

```text
Merit source
  -> concrete Merit-native replacement driver
  -> native source/function/declaration discovery
  -> typed/resolved semantics
  -> ownership/contracts/capabilities/control flow
  -> resolved multi-function MRBF bundle
  -> prepared replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
```

## Closure criteria

A semantic surface is CLOSED when all applicable columns are satisfied:

- **Reference:** Python/reference compiler accepts/rejects correctly.
- **Replacement:** production replacement compiler represents it without fallback.
- **Differential:** replacement agrees with reference for accepted/rejected cases.
- **Native:** generated C compiles and behaves identically.
- **Negative:** invalid cases fail closed with deterministic diagnostics/status.
- **Acceptance:** exercised by an acceptance application where applicable.
- **Determinism:** relevant serialized/generated artifacts are stable.
- **Windows:** covered by Windows native smoke where platform-relevant.

## Current coverage matrix

| Semantic surface | Reference | Replacement | Differential | Native | Negative | Acceptance | State |
|---|---:|---:|---:|---:|---:|---:|---|
| source lexing/tokenization | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| function discovery | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| multiple functions/source | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| basic let/var bindings | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| source ownership metadata | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| basic moves/drops | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| callable ownership and borrows | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| contracts | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| capability declarations | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| capability scopes/effects | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| payload-free enums | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| multiple enums | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| multiple match statements | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| typed match enum identity | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| multi-function MRBF | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| canonical replacement MIR | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| deterministic C emission | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| replacement executable | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| payload-bearing enums | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| complete branching/control flow | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| loops | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| rich owned structs/aggregates | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| strings/buffers complete alpha surface | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| exact decimal complete surface | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| bounded integers complete surface | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| generic functions/types | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| generic collections | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| coherent traits | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| cross-module imports | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| visibility/qualified names | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| stable exports/shared libraries | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| all alpha accepted corpus | ✓ | OPEN | OPEN | OPEN | — | — | OPEN |
| all alpha rejected corpus | ✓ | OPEN | OPEN | — | OPEN | — | OPEN |
| all nine acceptance projects | ✓ | OPEN | OPEN | OPEN | — | OPEN | OPEN |
| replacement default compiler path | — | OPEN | — | OPEN | OPEN | OPEN | OPEN |
| Python semantic authority removed | — | OPEN | — | — | — | — | OPEN |
| stage-0/stage-1 equivalence | — | OPEN | OPEN | OPEN | — | — | OPEN |
| reproducible alpha.2 release | — | OPEN | OPEN | OPEN | — | ✓ | OPEN |

`PARTIAL` is intentionally conservative. Replace it with concrete evidence rather than assuming coverage from neighboring tests.

### M1 evidence audit (2026-08-21)

The alpha.1 reference surface is exercised by the established compiler/project
suite. Replacement evidence must additionally reach the concrete native driver;
parser or isolated MIR fixtures do not close a production-path cell.

| M1 form | Alpha.1/reference evidence | Replacement evidence | Audit result |
|---|---|---|---|
| `let` / `var` / return | `tests/test_epoch_*.py`; acceptance projects | `tests/bootstrap/test_concrete_native_replacement_driver.py` drives source through native driver, MRBF, prepared artifacts, canonical MIR, C, and executable | production-proven |
| `if` / `else`, nested branches, early return | reference interpreter/native tests; `tests/project/test_bootstrap_mir_statement_lowering_gate.py` and `test_bootstrap_mir_structured_lowering_gate.py` prove native intermediate structure | `test_concrete_native_driver_closes_branch_loop_and_early_return_control_flow` compares reference/replacement executables and repeated bundles; malformed control flow is rejected deterministically | production-proven for scalar branch/return forms; aggregate row remains partial |
| `while`, nested loop control, loop exit | reference interpreter/native tests; the same statement/structured-MIR gates prove native intermediate structure | the concrete-driver closure test covers taken/untaken loops, nested branching, early return, mutable loop-carried assignment with per-iteration condition evaluation, deterministic artifacts, and native parity | production-proven for scalar loop forms; acceptance migration remains open |
| payload-free `match` integration | alpha.1 enum tests | concrete driver enum/typed-identity cases in `tests/bootstrap/test_concrete_native_replacement_driver.py` | production-proven for the payload-free subset; lifecycle work remains M2 |
| capability regions | alpha.1 capability tests | concrete driver capability catalog/scope case in `tests/bootstrap/test_concrete_native_replacement_driver.py` | production-proven |
| ordinary scalar assignment | alpha.1 assignment tests and reference interpreter/native compiler | `test_concrete_native_driver_closes_branch_loop_and_early_return_control_flow` exercises assignments in both branch arms and a loop through native discovery, ownership/control flow, MRBF, canonical MIR, C, and executable parity; immutable assignment is rejected deterministically | production-proven for direct scalar bindings |
| `replace` / owned path merges | alpha.1 ownership tests; `tests/project/test_bootstrap_owned_source_replace_merge_gate.py` | concrete-driver destructor and recursive-owned lifecycle cases execute `replace` through MRBF, canonical MIR, C, and reference parity; path-sensitive owned control-flow cases cover convergent branch state | production-proven for represented owned aggregates; remaining storage/resource shapes close with M2/M3 |
| pure expression statements | alpha.1 compiler tests and reference interpreter/native compiler | the concrete-driver assignment/control case evaluates `x+100;` through the production path; parser-oracle coverage distinguishes it from assignment and equality expressions | production-proven for the current scalar expression surface |
| `print` / `drop` | alpha.1 compiler and acceptance tests; parser recognizes both forms | scalar `print` and owned aggregate `drop` have native source records, ownership/control-flow placement, canonical MIR, deterministic C, and reference parity in the concrete-driver control-flow and lifecycle cases | production-proven for scalar print and represented owned aggregates; remaining resource shapes close with M2/M3 |

This audit deliberately leaves the aggregate `complete branching/control flow`
and `loops` rows OPEN: scalar accepted/rejected cases now traverse the complete
production path, but resource-effect statements and replacement-mode acceptance
coverage remain outstanding. The represented M1 `drop`/`replace` boundary now
has recursive lifecycle and destructor-backed production evidence. Unrepresented
resource/storage shapes remain owned by M2/M3 rather than a scalar compatibility
seam.

## Large remaining milestones

### M1 — Accepted-alpha statement/control-flow closure

**Goal:** Drive every remaining alpha.1 statement/expression/control-flow form through the production replacement pipeline.

Includes as applicable:

- conditionals;
- loops;
- returns and early termination;
- nested control flow;
- expression statements;
- assignment/replace;
- match integration;
- path-sensitive ownership across branches.

**Exit criteria:**

- relevant coverage cells CLOSED;
- accepted/rejected differential cases;
- interpreter/native parity;
- no Python fallback;
- full Local Gate green.

### M2 — Resource and payload-enum lifecycle closure

**Goal:** Close owned aggregate/resource semantics including payload-bearing enums.

Includes:

- recursive lifecycle classification;
- enum payload ownership;
- destructors;
- move/drop/replace semantics;
- early-return cleanup;
- no double destruction;
- negative ownership cases.

**Current production evidence:** `test_concrete_native_driver_executes_copy_payload_enum_lifecycle`
drives a Copy `i32` payload enum through native declaration discovery, symbolic
enum typing, constructor/tag/payload MIR, MRBF, prepared replacement artifacts,
deterministic C, and reference/replacement executable parity. Repeated native
driver output is byte-identical. The adjacent owned-`Buffer` payload case remains
fail-closed and publishes no replacement manifest. This closes only the Copy
single-payload subset; recursive owned payloads, mixed payload shapes,
destructors, and move/drop/replace cleanup remain open, so the matrix row and M2
remain `PARTIAL`/OPEN.

`test_concrete_native_driver_executes_non_copy_single_i64_struct_lifecycle`
adds production evidence for an exactly one-field `i64` non-copy struct. The
native source-unit catalog owns nominal struct/field identity; construction,
field access, ownership activation, implicit early-return cleanup, canonical
`drop`, explicit `drop`, direct-binding `move`, MRBF preparation, deterministic
C, and reference/replacement executable parity all traverse the concrete
replacement path. Repeated driver output is byte-identical. Wrong field
identities, unrepresented multi-field shapes, and `replace` on this non-copy but
no-destructor shape are rejected deterministically and publish no replacement
manifest. The rich-owned-aggregate row remains `PARTIAL`/OPEN because
multi-field and recursively owned
fields, observable destructors, replacement and branch-sensitive lifecycle
variants, and double-destruction coverage are still open.

PR #97 adds native recursive declared-type lifecycle classification across
struct and enum payload dependencies, with deterministic rejection of direct
self-payload cycles, unresolved payload types, and depth-bounded malformed
graphs in `test_bootstrap_recursive_type_lifecycle_gate.py`. This is concrete
native classification evidence, but it does not by itself close payload
construction or recursive destruction through the production executable path.

`test_concrete_native_driver_executes_observable_i64_struct_destructor_lifecycle`
adds the first observable destructor-backed production slice for an exactly
one-field `i64` struct. Native declaration records distinguish the exact
`print(self.field)` destructor policy from destructor-free structs; canonical
MIR and deterministic C execute implicit cleanup, explicit `drop`, direct move,
early-return cleanup, and `replace` with reference/replacement output parity.
The move case proves no double destruction, repeated native bundles are
byte-identical, and an unrepresented destructor body fails closed without a
replacement manifest. M2 remains OPEN because general destructor bodies,
owned fields and payload enums, multi-field aggregates, and branch/match
lifecycle convergence remain incomplete.

`test_concrete_native_driver_executes_owned_destructor_payload_enum_lifecycle`
extends that observable destructor policy through an owned payload enum on the
production replacement path. Native declaration discovery preserves nominal
enum and payload-struct identity; match payloads enter the canonical ownership
binding namespace; enum construction consumes its owned source; and match
transfers ownership from the consumed subject into exactly one arm-local
payload. Implicit enum cleanup, explicit `drop`, direct move, early-return
cleanup, `replace`, and a two-variant match all reach MRBF preparation,
canonical MIR, deterministic C, and reference/replacement executable parity.
Destructor output proves replacement drops the old value during `replace` and
does not double-destroy moved or matched payloads. Repeated native bundles are
byte-identical. A mixed Copy/owned payload shape is rejected deterministically
and publishes no replacement manifest. This closes the represented homogeneous
single-payload/destructor-struct vertical slice; general recursive payload
shapes, multi-field aggregates, and general destructor bodies keep the
payload-bearing-enum and rich-owned-aggregate rows `PARTIAL` and M2 OPEN.

`test_concrete_native_driver_executes_recursive_owned_aggregate_lifecycle`
extends the production path through acyclic single-field owned aggregate
nesting and an owned enum whose payload is such an aggregate. Native declaration
resolution emits canonical type descriptors into the resolved snapshot; the
Python handoff only validates and materializes those already-resolved schemas.
Implicit cleanup, explicit `drop`, direct move, early-return cleanup, `replace`,
and match-payload transfer all reach canonical MIR, deterministic C, and
reference/replacement executable parity. Observable nested destructor output
proves recursive cleanup and no double destruction after moves and match
transfer, while repeated native bundles prove deterministic transport.
`test_concrete_native_driver_fails_closed_for_recursive_owned_aggregate_cycle`
and the descriptor validation tests reject cyclic, unresolved, duplicate,
noncanonical, and unsupported schemas. This closes the acyclic single-field
recursive-owned slice; multi-field aggregates, general destructor bodies, and
the remaining alpha.1 resource shapes keep both aggregate rows and M2 OPEN.

`test_concrete_native_driver_executes_path_sensitive_owned_aggregate_control_flow`
drives represented recursive owned values through scoped `if`, `while`, and
match-arm bodies, convergent drops in both branch arms, scoped replacement
transfer, and drop-versus-early-return cleanup. Capability regions nested in a
branch preserve the enclosing ownership scope, while function-owned values
declared inside a capability region still receive function-epilogue cleanup.
Each accepted case compares reference and replacement executables and repeats
the native bundle to prove deterministic artifacts. Native source lowering now
emits explicit owned-binding scope exits in reverse declaration order; the
ownership state machine requires scoped values and owned match payloads to have
been moved or dropped, while terminated paths retain valid return cleanup. The
adjacent fail-closed test proves deterministic rejection and no manifest
publication for live scoped owners in branches, loops, and match arms;
branch-divergent reuse; double drop; and an unconsumed owned match payload, with
matching alpha.1 reference rejection categories. This closes path-sensitive
lifecycle behavior for the represented recursive-owned slice; general
destructor bodies, multi-field/resource aggregates, and acceptance migration
keep M2 OPEN.

`test_concrete_native_driver_executes_multi_field_owned_aggregate_lifecycle`
and the adjacent scalar/nested aggregate cases extend the production path from
single-field compatibility shapes to canonical arbitrary-arity aggregate
schemas. Snapshot v3 carries one ordered descriptor row per field; canonical
MIR identifies construction, stores, and loads by field ordinal; and C emission
orders dependent aggregate definitions and recursively destroys owned fields.
Named initializers are validated independently of source order. Implicit and
explicit cleanup, direct move, `replace`, and owned enum match transfer execute
multi-field values with deterministic native bundles and
reference/replacement executable parity. Observable destructors select a
declared scalar field without changing recursive field cleanup. Focused
fail-closed cases reject duplicate, missing, and unknown initializer fields,
unknown or duplicate destructor targets, cyclic multi-field graphs, and
malformed/noncanonical aggregate descriptors without publishing a replacement
manifest. This closes the general finite aggregate schema and represented
multi-field owned-lifecycle slice. General destructor bodies, the remaining
alpha.1 resource shapes, and acceptance migration keep M2 and the broad matrix
rows `PARTIAL`/OPEN.

`test_concrete_native_driver_executes_observable_i64_struct_destructor_lifecycle`
now closes the print-only destructor compatibility seam in favor of executable
destructor programs carried by resolved snapshot v4. The concrete native driver
discovers and lowers destructor `print` expressions, copy-field assignment,
`if`/`else`, `while`, and checked arithmetic into destructor-local records,
structured CFG, and instruction placements. Snapshot materialization reconstructs
a canonical `MirDestructor`; deterministic C executes that body exactly once
before recursive owned-field cleanup. The structured case mutates two values
through different branch/loop paths and matches reference output `10\n3\n` in
reverse cleanup order; constant-expression, implicit cleanup, explicit drop,
move/no-double-drop, early return, `replace`, owned-payload-enum, and recursive
aggregate lifecycle cases also retain reference/replacement parity. Repeated
native bundles are byte-identical. The adjacent ownership-changing-body case
fails closed deterministically and publishes no manifest, while snapshot tests
reject invalid/noncanonical descriptor ranges, duplicate targets, excess or
unreferenced body/CFG/placement rows. Canonical MIR round-trip and executable C
tests independently cover destructor-program validation and deterministic
emission. This closes general destructor bodies for the currently represented
M2 aggregate/expression surface. Callable ownership/borrow boundaries, general
payload-enum schemas and `try` lifecycle, and the minimal resource carriers still
keep M2 and the broad matrix rows `PARTIAL`/OPEN; imported destructor helpers
remain M5 rather than expanding this slice.

`test_concrete_native_driver_executes_owned_callable_transfer_lifecycle`,
`test_concrete_native_driver_executes_relayed_borrowed_callable_lifecycle`, and
`test_concrete_native_driver_executes_mutable_borrowed_callable_lifecycle` close
the alpha.1 callable ownership boundary through the production replacement
path. The native source catalog carries ordered parameter modes, return modes,
and borrowed-result parameter origins into MRBF and canonical MIR. Owned
arguments transfer into value parameters and owned returns transfer back to the
caller without double destruction; shared and mutable borrows relay their
caller origin without acquiring ownership; field reads and mutable field stores
through returned borrows remain ephemeral. The mutable target case emits an
observable effect from the borrow-returning call and proves that target is
evaluated exactly once. Each accepted case compares reference and replacement
executables and repeats native bundles for deterministic transport. The
adjacent rejection matrix covers immutable mutable-borrow arguments,
shared-to-mutable escalation, conflicting loans, moving an origin while loaned,
storing or value-passing a borrowed return, inconsistent return origins, and
dropping a borrowed parameter; native rejection is deterministic and publishes
no replacement manifest. The exact remaining M2 blockers are heterogeneous
user payload-enum schemas and owned `try` success/error propagation; the
`FileReadResult` `ReadOk(Buffer)`/`ReadErr(i32)` and `FileWriteResult`
`WriteOk(i64)`/`WriteErr(i32)` lifecycle shapes; and the minimum direct `Buffer`
move/drop/replace cases plus `Buffer` as an owned struct or enum field. That
last group includes owned-field replacement through a returned mutable borrow.
Only the construction and operations needed to prove those ownership transfers
belong to M2; the complete Buffer, String, decimal, bounded, and aggregate
operation surfaces remain M3, while generic `Vec<T>` lifecycle remains M4.

`test_concrete_native_driver_executes_mixed_owned_payload_enum_lifecycle`, the
owned-`try` success/error matrix, the direct and aggregate `Buffer` lifecycle
cases, and the structural filesystem-result matrix close those audited gaps on
the production replacement path. Snapshot v5 carries heterogeneous payload
types by canonical variant ordinal; owned construction and `try` propagation
consume their sources exactly once; match transfers owned payloads into the
selected arm; and implicit cleanup, explicit `drop`, direct `replace`, and
early-return cleanup preserve reference/replacement executable parity. Direct
`Buffer` move/drop/replace, recursively owned struct and enum fields, and field
replacement through a returned mutable borrow reach MRBF, canonical MIR, and
deterministic C. The mutable-borrow case emits an observable call-side effect
exactly once and drops only the prior field before storing the moved
replacement.

`test_concrete_native_driver_executes_predefined_filesystem_result_lifecycle`
adds the exact predefined `FileReadResult` and `FileWriteResult` identities,
including `ReadOk(Buffer)`, `ReadErr(i32)`, `WriteOk(i64)`, and
`WriteErr(i32)`, to the native canonical enum catalog. Match identity now comes
from that catalog rather than rescanning only textual enum declarations. The
direct-drop case proves that a predefined result remains represented when an
unused variant spelling is absent from the function source; the match cases
exercise all canonical variant names, owned payload transfer, deterministic
bundles, prepared artifacts, generated C, and reference/replacement parity.
The adjacent malformed-schema, ownership, borrow, double-destruction, and
fail-closed cases remain authoritative negative evidence.

M2 is **CLOSED**. The payload-bearing-enum matrix row is closed for the
documented alpha.1 surface. The broader rich-aggregate and complete
String/Buffer rows intentionally remain `PARTIAL`/OPEN because their remaining
operations belong to M3; generic `Vec<T>` lifecycle remains M4, imported helper
resolution remains M5, and general acceptance-project migration remains M7.

### M3 — Exact numerics and aggregate closure

**Goal:** Move the complete alpha.1 decimal/bounded/string/buffer/aggregate surface through replacement compilation.

`test_concrete_native_driver_resolves_exact_numeric_declaration_descriptors`,
`test_concrete_native_driver_executes_exact_numeric_literals`, and
`test_concrete_native_driver_executes_exact_numeric_arithmetic_and_rounding`
carry native-resolved decimal precision, scale, and all five rounding policies,
plus signed and full-width unsigned bounded domains, through snapshot v6, MRBF,
prepared replacement artifacts, canonical MIR, deterministic C, and executable
reference/replacement parity. Decimal and bounded addition, subtraction,
multiplication, division, comparisons, negative rounding, and formatted output
use the declared nominal domain rather than a Python-inferred compatibility
type. The primitive integer companion case covers `i8`/`i16`/`i32`/`i64` and
`u8`/`u16`/`u32`/`u64` checked arithmetic and comparisons through the same
path. Repeated native bundles are byte-identical.

`test_concrete_native_driver_preserves_exact_numeric_runtime_failures` and the
snapshot/C-emitter validation suites preserve deterministic overflow,
out-of-domain, division-by-zero, malformed descriptor, and noncanonical range
failure behavior. Oversized unsigned bounds are transported as canonical
sign/high/low magnitudes, so the Python handoff validates already-resolved
numeric schemas rather than becoming their semantic authority.

`test_concrete_native_driver_executes_exact_numeric_aggregate_fields` composes
decimal and bounded fields with the arbitrary-arity aggregate schema already
closed by M2. Named initializer order, field ordinals, nominal field types,
field access, arithmetic on loaded fields, cleanup, generated C, and executable
output all agree with the reference path. This supplies the remaining M3
aggregate evidence without reopening the ownership/lifecycle work closed in
M2.

`test_concrete_native_driver_executes_utf8_string_surface` preserves UTF-8 byte
spans and covers String printing, byte length, byte indexing, and the documented
out-of-range zero result. `test_concrete_native_driver_executes_buffer_and_slice_surface`
covers system and portable allocator identity, compatibility, `buffer_new`,
`buffer_from_string`, growth via `buffer_push`, direct Buffer printing,
`buffer_len`, `buffer_get`, `buffer_allocator`, `buffer_slice`, `slice_len`, and
`slice_get`, while retaining independent per-test project/output directories.
The adjacent runtime-failure matrix preserves negative-capacity and Buffer/
ByteSlice bounds failures; the direct native-driver capability matrix rejects
allocating Buffer operations outside an authorized `allocate` scope. Existing
M2 cases remain the lifecycle authority for Buffer move/drop/replace, aggregate
fields, and payload enums.

M3 is **CLOSED**. The rich aggregate, complete String/Buffer, exact decimal,
and bounded-integer matrix rows are closed for the documented alpha.1 surface.
Generic `Vec<T>` operations remain M4, module/visibility/stable-export behavior
remains M5, complete corpus convergence remains M6, and replacement-mode
migration of the exact-decimal ledger and the other acceptance applications
remains M7.

### M4 — Generics and traits closure

**Goal:** Move explicit generics, generic collections, coherent trait resolution and instantiated operations through replacement compilation.

Do not introduce a second generic/trait semantic model.

`test_generic_trait_impl_identities_are_native_and_source_order_independent`
and the native generic-expansion gate establish canonical generic declarations,
ordered parameters and bounds, exact concrete trait-implementation lookup, and
source-order-independent trait identities in Merit-native code. Generic
functions, structs, payload enums, user-trait method dispatch, and the builtin
`Vec<T>` surface are specialized to concrete nominal declarations and calls
before source-function discovery and MIR lowering. No generic MIR or recursive
trait solver is introduced; Alpha.1 has no syntax for recursive implementation
requirements, so trait-resolution cycle semantics are not part of this
milestone.

`test_concrete_native_driver_monomorphizes_generic_function_before_mir`,
`test_concrete_native_driver_monomorphizes_generic_struct_and_payload_enum_before_mir`,
and `test_concrete_native_driver_uses_static_user_trait_dispatch_before_mir`
carry those concrete expansions through MRBF, prepared replacement artifacts,
canonical MIR, deterministic C, native execution, and reference/replacement
parity. Specialization preserves source parameter order and ordinary concrete
ownership modes rather than assigning meaning from generated binding IDs.
`test_concrete_native_driver_uses_ordinary_ownership_for_generic_calls` proves
owned argument/return transfer and borrowed observation for a concrete
`Buffer` specialization.

`test_concrete_native_driver_executes_vec_i64_lifecycle_before_mir` and
`test_concrete_native_driver_executes_owned_and_nested_vec_lifecycle_before_mir`
close the documented Alpha.1 generic collection surface. They cover allocation,
push, length, get, set, replace, pop, allocator retention, transfer, explicit
and implicit drop, moved-out elements, recursively nested vectors, and element
destructors. Canonical vector type descriptors survive snapshot transport;
generated C uses type-directed helpers and recursively destroys live owned
elements exactly once. Repeated native bundles are byte-identical and both
primitive and owned/nested cases execute with reference/replacement parity.

`test_concrete_native_driver_fails_closed_for_invalid_generic_trait_and_vec_semantics`
provides the adjacent rejection evidence for wrong generic arity, missing and
duplicate trait implementations, ambiguous trait methods, unsatisfied `Copy`
bounds, generic use-after-move, moved-vector reuse, illegal owned-element
copy-out, and vector allocation without capability. Rejection is deterministic
at the earliest authoritative replacement boundary and never publishes a
replacement manifest. Existing Alpha.1 generic and trait tests remain the
independent Python-oracle evidence.

M4 is **CLOSED**. Generic acceptance-project migration remains M7, and imported
generic declarations, visibility, qualified names, exports, and shared-library
interactions remain M5.

### M5 — Module/project closure

**Goal:** Close multi-source-unit compilation, imports, qualified names, visibility, exports, stable-layout/shared-library interactions.

`test_concrete_native_driver_compiles_qualified_multimodule_project_as_one_bundle`
drives four source units through one deterministic canonical project source and
one native MRBF bundle. Imported types, functions, traits, generic
instantiations, qualified constructors/calls, and an imported destructor helper
reach prepared artifacts, canonical MIR, deterministic C, native execution, and
reference/replacement parity. Published project source and source digests are
validated on consumption, so changed units reject stale artifacts.

Snapshot v9 carries native-derived aggregate type/member spans plus public and
stable flags in the existing type-descriptor contract. Export identity remains
in the canonical function header. The replacement shared-library path consumes
only that native metadata to emit public prototypes, stable aggregate typedefs,
and deterministic size/offset assertions. It rejects unrepresented or
non-public/non-stable aggregate ABI types rather than reparsing source or
inventing a layout. `test_concrete_native_driver_builds_public_scalar_shared_library_from_project_bundle`
proves private `main` exclusion, scalar and stable-aggregate exports, generated
header layout, native shared linking, and foreign `ctypes` calls. The project
CLI exposes this path through `build-shared --compiler replacement` and retains
its no-reference-fallback rule.

Existing Alpha.1 project diagnostics remain the negative authority for missing
imports, unimported qualification, private ABI leaks, and nested private type
exposure. Replacement preparation additionally fails closed on missing,
malformed, stale, or source-inconsistent project artifacts and never silently
uses reference lowering.

M5 is **CLOSED**. Complete accepted/rejected corpus convergence remains M6;
general acceptance-project migration remains M7; normal production cutover,
reproducibility/trust, and release audit remain M8-M10.

**Deferred bootstrap compiler defect discovered during M5:** threading one
additional scalar `exported:i32` argument through
`print_resolved_source_function_bundle_item` into the existing large
`print_resolved_source_function_snapshot` call serialized the complete snapshot
but then returned corrupted status `1392`; the production driver wrapped that
as status `4392`. The minimal trigger is a two-function source containing a
public `fn identity(value:i32)->i32 { return value; }` and a `main` that calls
it, after adding the scalar argument to those two snapshot-print signatures and
forwarding it unchanged. Export identity is instead encoded canonically in the
function-header record in snapshot v8. The large-call/status-corruption defect
is real but does not block M5 and is deferred to a dedicated bootstrap call-ABI
repair; do not treat the representation change as its fix.

### M6 — Corpus convergence

**Goal:** Run the complete alpha.1 accepted and rejected corpus against reference and replacement compilers and eliminate every unexplained discrepancy.

Output should be an executable/generated coverage report where practical.

### M7 — Acceptance migration

**Goal:** All nine alpha acceptance projects compile/run through replacement mode with no Python semantic lowering.

The exact-decimal ledger is mandatory evidence.

### M8 — Production cutover

**Goal:** Make replacement compilation the normal compiler path for the alpha surface.

Python becomes explicitly reference/oracle-only.

No silent fallback.

### M9 — Trust/reproducibility

**Goal:**

- stage-0 produces stage-1;
- repeated stage builds are deterministic;
- canonical artifacts are equivalent under the documented comparison rule;
- clean environment reproduction succeeds.

### M10 — Alpha.2 release closure

**Goal:**

- STATUS/ROADMAP/BOOTSTRAP_STATUS/manual synchronized;
- limitations accurate;
- complete release gate green;
- clean-tree reproducibility confirmed;
- alpha.2 release notes prepared.

## PR sizing policy

Prefer one PR per milestone above where practical.

Split a milestone only when:

1. a genuinely independent architectural prerequisite is discovered;
2. the PR becomes impossible to validate coherently;
3. separate changes have materially different rollback/trust boundaries.

Do **not** split merely because a change touches many files or exceeds an arbitrary line count.

Do **not** add temporary compatibility seams when the final alpha.2 representation can reasonably be implemented and tested in the same PR.

## Alpha.2 semantic numeric cleanup freeze

While alpha.2 remains open, do not perform repository-wide or opportunistic
cleanup of existing semantic magic numbers. Existing magic numbers may be
changed only when required to complete the current alpha.2 work, and any
required change must stay within the smallest practical scope.

Do not expand an alpha.2 PR merely because nearby existing magic-number debt is
discovered. Defer that debt to a dedicated post-alpha.2 cleanup PR.

This temporary restriction expires when alpha.2 is formally closed and tagged.
Expiration removes only this cleanup freeze; the permanent `AGENTS.md` rule
against introducing new semantic magic numbers remains in force.

## Testing cadence

During development:

```text
specific failing test
    ↓
focused test file
    ↓
affected subsystem
    ↓
full scripts/ci.sh
```

Do not run the full suite after every small edit.

GitHub Local Gate remains authoritative before merge.

## Failure handling

Large test counts often fan out from one compiler/bootstrap failure.

When the suite fails:

1. inspect the first meaningful failure;
2. determine the shared root cause;
3. fix the root cause rather than individual downstream tests;
4. run focused tests;
5. run the full gate once the root repair passes.

## Completion condition

Alpha.2 is complete when:

1. the documented alpha.1 accepted surface compiles through replacement mode;
2. the documented rejected surface remains rejected;
3. reference/replacement semantic parity is demonstrated;
4. all acceptance applications pass;
5. normal production compilation no longer uses Python semantic lowering;
6. deterministic stage/reproducibility criteria pass;
7. release documentation and limitations match reality.
