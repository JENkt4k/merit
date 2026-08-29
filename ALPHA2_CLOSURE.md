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
| payload-bearing enums | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | — | OPEN |
| complete branching/control flow | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| loops | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| rich owned structs/aggregates | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| strings/buffers complete alpha surface | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| exact decimal complete surface | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| bounded integers complete surface | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| generic functions/types | ✓ | OPEN/PARTIAL | OPEN | OPEN | partial | partial | OPEN |
| generic collections | ✓ | OPEN/PARTIAL | OPEN | OPEN | partial | partial | OPEN |
| coherent traits | ✓ | OPEN/PARTIAL | OPEN | OPEN | partial | partial | OPEN |
| cross-module imports | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| visibility/qualified names | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| stable exports/shared libraries | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
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

### M3 — Exact numerics and aggregate closure

**Goal:** Move the complete alpha.1 decimal/bounded/string/buffer/aggregate surface through replacement compilation.

### M4 — Generics and traits closure

**Goal:** Move explicit generics, generic collections, coherent trait resolution and instantiated operations through replacement compilation.

Do not introduce a second generic/trait semantic model.

### M5 — Module/project closure

**Goal:** Close multi-source-unit compilation, imports, qualified names, visibility, exports, stable-layout/shared-library interactions.

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
