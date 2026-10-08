# SH3 capability matrix

This is the authoritative **SH3 burn-down** under the scope and exit contract
in `SELF_HOSTING.md`. It is not an Alpha.3 plan. Update a row only after its
stated evidence runs against the current tree; a later tree change makes the
affected evidence stale. Do not replace a family with a sequence of one-project
fixes or mark a family complete because one probe advances to a later error.

## Baseline and comparison boundary

- Inventory baseline: committed branch `self-hosting/sh3-native-mir-backend` at
  `db41df3`. The uncommitted catalog-aware MIR type writer is **not** included
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

## Finite capability families

`Open` means known missing or incomplete. `Partial` means focused evidence
exists for a subset, not the complete family. `Unverified` means the source
surface exists but there is no sufficient end-to-end SH3 evidence.

| ID | Shared implementation mechanism and remaining dependency | Current evidence/status | Completion evidence before closing row |
| --- | --- | --- | --- |
| F1 | **Canonical type graph.** Reconstruct the exact Alpha.2 `MirType` JSON for builtin, aggregate/stable-ABI structs, copy/owned payload enums, nested `Vec`, decimal, and bounded types from native type/numeric descriptors. Validate child graph, order, identity, source spans, policy, and cycles. Use the same catalog for function return, parameters, locals, instructions, and destructors. | **Partial (uncommitted).** `test_merit_catalog_types_match_python_mir_json` passes against `_descriptor_type_names` and `_numeric_descriptor_type_names` for builtin, nested vector, copy/owned-payload enum, owned-field struct, stable-ABI aggregate, decimal, bounded i64 extremes, and legacy copy-enum/i64-struct names. Cyclic and invalid-decimal catalogs reject. Focused owned-CFG and sourced-contract-local tests pass after numeric threading. The production materializer now uses the catalog for normal locals, contract locals, and return types. Other malformed catalogs, full function/project parity, and all instruction/destructor type use sites remain open. Seven committed-baseline acceptance requests stop at `4129`. | Focused valid/malformed descriptor cases; byte-identical canonical MIR against independent Python materialization for each type family and nested combination; accepted projects advance without type failure; no schema/ABI reinterpretation. |
| F2 | **Canonical function, CFG, and effect assembly.** Preserve block/terminator ordering, placements, source-local IDs, calls, aggregate instructions, contracts, capabilities, explicit ownership effects, return modes, and diagnostics for malformed records. | **Partial (uncommitted).** A focused out-of-order/reachable-block fixture reproduced native status `7`; sorting reachable blocks by ID and pruning reserved joins now matches canonical Python MIR. Reordered placement rows reproduced status `21`; a single materializer-boundary normalization now sorts by block-local ordinal and rejects gaps/duplicates. A malformed terminator in an unreachable block returns status `12` rather than disappearing. The two-record CFG path no longer reads a nonexistent instruction before target validation. Generated-C inspection exposed and fixed an early-return epilogue that dropped the new reachability vector before initialization (native exit `89`). Ownership placement, sourced contract locals, required capability names, and callable ownership metadata pass together (`4 passed in 119.40s`). A type-aware constant writer fixes the observed v4 `i32` JSON-string mismatch; direct MIR cases pass after correcting typed oracle expectations (`5 passed in 183.97s`, then the branch case `1 passed in 17.54s`). All eight fixed-width integer types pass in-range canonical MIR byte comparisons (`8 passed in 245.78s`), including corrected source/spans `i8` evidence (`1 passed in 30.89s`); five overflow/unsigned-negative cases reject (`5 passed in 143.46s`). The shared C integer validator passes its four existing i32/i64 byte-oracle and three invalid-value fixtures (`7 passed in 210.90s`); C emission for other widths is not proved. String constants decode and re-encode canonical JSON; seven escaped/raw UTF-8 cases pass exact MIR bytes, Python C/header comparison, and GCC execution (`1 passed in 35.69s`). Numeric descriptors now reach sourced body/contract literal emission. Four bounded direct cases pass, including the contract-domain exception and a `u64` value above `i64` range (`4 passed in 123.28s`); seven decimal direct cases match the Python materializer or reject excess scale/precision (`7 passed in 198.42s`). Whole-function/project numeric artifact parity and broader malformed-source cases remain open. `ledger_app` committed-baseline status `4107` still needs a fresh native compiler candidate before claiming resolution. | Accepted/rejected CFG and resource-effect differential matrix, including nested match, loop, early return, owned cleanup, contracts/capabilities, and deterministic bytes; `ledger_app` advances or its root mismatch is resolved without relaxing validation. |
| F3 | **Project-wide canonical assembly and destructors.** Collect all source-backed functions, preserve module/visibility identity, reject duplicate/conflicting functions and destructors, normalize payload-free enum storage only at the established representation boundary, and include destructor MIR in the project artifact. | **Open.** The native driver accumulates destructor descriptors but the v4 canonical/C finish path only appends ordinary functions. Python `replacement_project.py` performs duplicate/destructor validation and payload-free storage normalization. | Multi-module and destructor fixtures compare complete MIR/C bytes; duplicate/conflict/missing catalog cases fail closed; ownership lifecycle and native execution match the oracle. |
| F4 | **C type/layout and runtime feature closure.** Emit the oracle's aggregate/enum, stable-layout, numeric, nested vector, filesystem result, string/slice, allocator, and recursive cleanup declarations and helpers in dependency order. Keep semantic ownership separate from C storage strategy. | **Partial (uncommitted).** The native scalar C spelling table now covers all 14 builtin MIR types and passes a direct `_type(MirType(...))` oracle test (`1 passed in 30.46s`). A shared parameter/source-local/temporary admission rule now covers all fixed-width integer types without admitting `unit` or unknown builtins; its focused interpreter/native check passed (`1 passed in 30.92s`). This removes a known duplicated whitelist behind `4410` but does not establish that any acceptance project has advanced: the candidate has not been rebuilt and swept since this edit. Function/call validation still intentionally fails closed for unsupported operations, layouts, and runtime helpers. Native C emission otherwise covers scalar String/Buffer/ByteSlice and copy-vector names/runtime; `canonical_c_append_type_with_catalog` does not yet cover aggregate/enum/numeric graphs. Fresh pre-edit acceptance statuses `4410`/`4403` indicate this family. | Exact C/header bytes for each type/runtime family, GCC compilation and interpreter/native execution, layout assertions, deterministic order, malformed descriptor rejection. |
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
