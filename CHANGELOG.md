# Changelog

## Epoch III — Structured diagnostic checkpoint

- Added stable structured diagnostic payloads with source ranges and related notes.
- Added JSON diagnostic output to compiler and project CLIs.
- Preserved existing human-readable diagnostics as the default.
- Ensured syntax and project-system failures never fall back to mixed text in JSON mode.
- Increased the regression suite from 190 to 195 tests.

## Epoch III — Qualified import checkpoint

- Added explicit `module.symbol` resolution for imported functions, types, and constructors.
- Preserved source columns during project qualification preprocessing.
- Added missing-import diagnostics and interpreter/native parity coverage.
- Increased the regression suite from 188 to 190 tests.

## Epoch III — Content-addressed object-cache checkpoint

- Split project C compilation from executable/shared linking.
- Added content-addressed object caching keyed by source, compiler, flags, and PIC mode.
- Added deterministic reuse coverage for repeated identical builds.
- Added resolved compiler-binary identity and flag-change invalidation coverage.
- Increased the regression suite from 187 to 188 tests.

## Epoch III — C shared-library acceptance checkpoint

- Added project `build_shared` support and the `build-shared` CLI command.
- Emitted PIC shared objects alongside generated C headers.
- Added a foreign-caller smoke test for a generated primitive ABI function.
- Preserved merged-project `pub` exports and filtered private functions from consumer headers.
- Added foreign-caller acceptance for stable-layout structs passed by value.
- Rejected private-type leakage through public functions, structs, and enums.
- Filtered private structs and enums from project consumer headers.
- Increased the regression suite from 185 to 187 tests.
- Increased the regression suite from 184 to 185 tests.

## Epoch III — MIR constant branch checkpoint

- Folded exact literal/arithmetic/comparison branch conditions to direct MIR gotos.
- Matched untyped literal and division folding to runtime `i64` semantics.
- Preserved folded conditions in explicit MIR and pruned dead successor blocks.
- Increased the regression suite from 182 to 184 tests.

## Epoch III — MIR reachability checkpoint

- Added entry-rooted reachability analysis after MIR CFG construction.
- Removed synthetic unreachable continuation blocks after terminal returns.
- Increased the regression suite from 181 to 182 tests.

## Epoch III — Borrowed return diagnostic checkpoint

- Added explicit `borrow` and `borrow_mut` function return modes.
- Added borrowed-parameter origin and mutable-origin lifetime diagnostics.
- Kept otherwise-valid borrowed returns gated until caller tracking and parity-safe lowering are complete.
- Increased the regression suite from 177 to 181 tests.

## Epoch III — Multiple allocator provider checkpoint

- Added deterministic `portable_allocator()` alongside `system_allocator()`.
- Routed both providers through the same stored-allocator vector growth/drop implementation.
- Added provider-parameterized interpreter/native parity coverage.
- Increased the regression suite from 176 to 177 tests.

## Epoch III — Allocator-retaining generic collections checkpoint

- Added allocator identity to concrete `Vec<T>` runtime and layout records.
- Routed vector growth and destruction through the allocator stored at construction.
- Added interpreter metadata and generated-C assertions for allocator retention.
- Increased the regression suite from 175 to 176 tests.

## Epoch III — Typed filesystem error checkpoint

- Changed `file_read` and `file_write` to return built-in nominal result enums.
- Added stable `FsNotFound`, `FsPermissionDenied`, and `FsIoError` categories.
- Added interpreter/native failure parity coverage while preserving lexical capability gates.
- Increased the regression suite from 174 to 175 tests.

## Epoch III — Typed parser intermediate checkpoint

- Replaced field-initializer tuples with immutable `FieldInitializer` records.
- Replaced effects, capability, and contract tag tuples with immutable `FunctionClause` records.

## Epoch III — Typed parser declaration checkpoint

- Replaced top-level parser declaration-tag tuples with immutable `DeclarationEntry` records.
- Migrated impl-method extraction and program symbol assembly to named declaration fields.

## Epoch III — Typed parameter checkpoint

- Added immutable `Parameter` records shared by functions and trait methods.
- Migrated semantic, ownership, interpreter, native, MIR, and project consumers to named parameter fields.
- Added explicit JSON-safe parameter serialization to MIR output.

## Epoch III — Semantic naming and typed match-arm checkpoint

- Renamed the typed semantic storage base from `SemanticTuple` to `SemanticNode`.
- Replaced compact match-arm tuples with immutable `MatchArm` records.
- Added explicit recursive serialization and parity coverage for typed match arms.
- Increased the regression suite from 173 to 174 tests.

## Epoch III — Named semantic access checkpoint

- Removed indexed sequence compatibility from semantic nodes.
- Migrated project visibility traversal and compiler literal validation to named node properties.
- Retained raw tuples only for non-node parser records pending typed decomposition.

## Epoch III — Immutable semantic storage checkpoint

- Replaced Python tuple inheritance with immutable typed semantic sequence storage.
- Tightened compiler and project traversal to identify semantic nodes by their typed base.
- Restricted source-provenance updates to controlled internal attachment paths.

## Epoch III — Canonical explicit MIR checkpoint

- Migrated repository MIR consumers to JSON-safe `semantic_blocks`.
- Removed raw tuple-compatible MIR blocks from public output.

## Epoch III — Explicit semantic serialization checkpoint

- Added JSON-safe kind/operand/provenance serialization for semantic nodes.
- Migrated HIR function output to explicit semantic serialization.
- Added explicit MIR `semantic_blocks` alongside compatibility blocks.
- Increased the regression suite from 172 to 173 tests.

## Epoch III — Typed function consumer checkpoint

- Migrated semantic, ownership, interpreter, C, MIR, and project consumers to typed function fields.
- Made mapping compatibility read-only.
- Migrated generated implementation naming to typed field mutation.
- Preserved the 172-test interpreter/native parity baseline.

## Epoch III — Typed function declaration checkpoint

- Replaced dictionary-subclass functions with typed `FunctionDecl` records.
- Preserved mapping compatibility for incremental consumer migration.
- Added explicit HIR function serialization and JSON coverage.
- Increased the regression suite from 171 to 172 tests.

## Epoch III — Fully embedded provenance checkpoint

- Embedded provenance on declaration dataclasses and `FunctionDecl` records.
- Migrated duplicate-symbol and project declaration remapping to embedded locations.
- Removed `Program.spans` and `Program.related_spans` entirely.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Semantic provenance map-retirement checkpoint

- Removed duplicate semantic-node entries from primary and related ID maps.
- Remapped embedded semantic provenance directly during project assembly.
- Retained external maps only for declaration/function records.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Embedded semantic-node provenance checkpoint

- Embedded typed primary/related provenance on every concrete semantic node.
- Made `Program.provenance()` prefer embedded locations with compatibility fallback.
- Refreshed embedded locations after project-unit remapping.
- Verified semantic provenance remains available after clearing legacy maps.
- Preserved the 171-test interpreter/native parity baseline.

## Development tooling — Python launcher portability

- Made bootstrap select `python` or `python3` instead of requiring a `python` command.
- Preserved explicit failure when no Python 3 launcher is available.

## Epoch III — Precise diagnostic range checkpoint

- Extended rendered primary and related diagnostics with end-column ranges.
- Underlined complete semantic spans rather than only their first column.
- Added rendered generic-range coverage.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Column-precise generic provenance checkpoint

- Recorded exact generic application start/end columns during expansion.
- Used precise ranges for arity and bound diagnostics.
- Preserved exact related instantiation ranges for generated-body diagnostics across projects.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Typed semantic provenance boundary checkpoint

- Added `NodeProvenance` for typed primary and related source locations.
- Centralized semantic provenance lookup in `Program.provenance()`.
- Migrated semantic views and checker diagnostics off direct metadata-map access.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Complete per-kind semantic variant checkpoint

- Added per-kind variants for string, number, variable, and struct-initializer nodes.
- Distinguished direct and generic call storage.
- Added per-kind return, print, expression-statement, and drop variants.
- Completed concrete runtime typing for every parser-produced semantic expression and statement.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Safety-critical per-kind variant checkpoint

- Added distinct variants for ordinary bindings, `try`, assignment, and replacement.
- Added distinct variants for capability scopes, branches, loops, and matches.
- Preserved family inheritance and tuple-compatible serialization.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Typed semantic storage-family checkpoint

- Added concrete storage families for expression and statement categories.
- Routed parser construction through a deterministic semantic-kind storage registry.
- Added runtime storage-family assertions for control flow, bindings, calls, and replacement.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Concrete semantic storage checkpoint

- Added tuple-compatible `SemanticTuple` storage with explicit kind and operand surfaces.
- Migrated parser construction for every semantic expression and statement.
- Kept `SemanticNodeView` as the typed accessor and provenance facade.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Typed expression-operand checkpoint

- Migrated atom, field, constructor, call, generic-call, and binary operands to named accessors.
- Removed positional expression operand reads from ownership, checking, interpreter, and C lowering.
- Migrated recursive expression walkers to the typed operand collection.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Typed statement-operand checkpoint

- Added named mutability and capability-region accessors.
- Migrated remaining `try`, match, branch, loop, and capability statement operands.
- Removed positional statement operand reads from checker, ownership, MIR, interpreter, and C lowering.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Typed helper-dispatch checkpoint

- Migrated type and layout discovery to typed node accessors.
- Migrated ownership path/root and interpreter assignment helpers.
- Migrated C contract, cleanup, statement-walking, and address helpers.
- Removed remaining direct tuple-tag reads from semantic expression/statement dispatch.
- Preserved the 171-test interpreter/native parity baseline.

## Epoch III — Call and control-flow accessor checkpoint

- Added typed accessors for calls, generic arguments, fields, constructors, binary expressions, and control flow.
- Migrated call resolution to the typed semantic view.
- Migrated checker, interpreter, and MIR branch/match paths to named operands.
- Added call and control-flow accessor coverage.
- Increased the regression suite from 170 to 171 tests.

## Epoch III — Ownership-sensitive node accessor checkpoint

- Added named typed accessors for bindings, initializers, assignment/replacement operands, statement expressions, and drops.
- Migrated ownership-sensitive checker and shared analysis paths off positional operands.
- Migrated corresponding interpreter and C lowering paths while preserving replacement ordering.
- Added semantic accessor and replacement operand coverage.
- Increased the regression suite from 169 to 170 tests.

## Epoch III — Typed backend-dispatch checkpoint

- Migrated MIR control-flow dispatch to `SemanticNodeView`.
- Migrated interpreter statement and expression dispatch to the typed boundary.
- Migrated C statement, expression-type, and expression dispatch to the typed boundary.
- Preserved all interpreter/native behavior and the 169-test baseline.

## Epoch III — Typed semantic-node adapter checkpoint

- Added a typed semantic-node view with kind, operand, span, and related-provenance access.
- Added `Program.node()` as the compatibility boundary for tuple-backed nodes.
- Migrated checker and shared ownership analysis dispatch to the typed interface.
- Preserved interpreter and native backend behavior behind the compatibility representation.
- Increased the regression suite from 168 to 169 tests.

## Epoch III — Generic expansion diagnostics checkpoint

- Added source locations to generic arity and trait-bound expansion errors.
- Preserved structured expansion errors through merged-project loading.
- Remapped project expansion failures to the concrete calling unit.
- Added single-source and cross-project expansion diagnostic coverage.
- Increased the regression suite from 165 to 168 tests.

## Epoch III — Declaration diagnostics checkpoint

- Preserved spans for type, field, trait, implementation, and function declarations.
- Added precise locations to duplicate, unknown-type, numeric-policy, trait-signature, and declaration capability errors.
- Unwrapped compiler errors raised by AST transformation for consistent structured rendering.
- Added four declaration diagnostic regression cases.
- Increased the regression suite from 161 to 165 tests.

## Epoch III — Cross-project generic provenance checkpoint

- Recorded concrete instantiation locations for generated generic semantic nodes.
- Remapped template and related instantiation spans to their owning project units.
- Rendered related notes from their own source files.
- Preserved source lines while preprocessing module and import declarations.
- Added a cross-module template/instantiation diagnostic regression test.
- Increased the regression suite from 160 to 161 tests.

## Epoch III — Local generic source-map checkpoint

- Preserved original line structure while extracting generic templates.
- Mapped semantic nodes in monomorphized bodies back to their template lines.
- Added diagnostics for generated-body failures and for ordinary declarations following templates.
- Increased the regression suite from 158 to 160 tests.

## Epoch III — Broad semantic diagnostics checkpoint

- Preserved spans for literals, constructors, calls, arithmetic, declarations, assignments, replacement, returns, capability regions, and control flow.
- Attached actionable primary locations to type, capability, replacement, exhaustiveness, constructor, field, and call diagnostics.
- Added rendered diagnostic regression tests for the principal semantic error families.
- Increased the regression suite from 154 to 158 tests.

## Epoch III — Project semantic diagnostics checkpoint

- Remapped merged-project semantic spans to their owning source units.
- Added structured `CompileError` rendering to every checking project workflow.
- Added the same structured semantic rendering to the single-source CLI.
- Added project check/build/run/verify/audit diagnostic regression coverage.
- Added multi-module ownership diagnostics that identify the correct non-entry file.

## Epoch III — Source-aware ownership diagnostics checkpoint

- Preserved source spans and source identity for variable, field, and drop nodes.
- Added move and drop origins to ownership state, including branch and loop merges.
- Added structured compile errors with primary spans and related notes.
- Rendered use-after-move and use-after-drop diagnostics with both source excerpts.
- Exposed ownership consumption sites in MIR.
- Added single-source, branch-flow, rendered diagnostic, MIR provenance, and project-merge tests.

## Epoch III — Typed semantic metadata checkpoint

- Added a cached concrete type table for ownership, copyability, drop requirements, semantic kinds, and drop strategies.
- Replaced vector ownership booleans with declarative element policies evaluated against type metadata.
- Added a shared function ownership-effects model for owned locals, consumed roots, and explicit drops.
- Migrated MIR and native epilogue cleanup to the shared ownership effects.
- Fixed duplicate native cleanup after direct owned local moves.
- Added metadata-driven recursive interpreter destruction for buffers, vectors, structs, and enums.
- Exposed type semantics in HIR and ownership effects in MIR.
- Added direct-move native parity, nested consuming-call, lifecycle metadata, and recursive destruction tests.

## Epoch III — Explicit owned replacement checkpoint

- Added `replace(target, replacement)` for mutable owned locals, owned fields, and mutable borrowed parameters.
- Defined replacement order as evaluate once, drop the displaced owner, then install and consume the replacement.
- Added checked `vec_replace<T>` for owned vector elements.
- Added conservative source/target alias rejection.
- Preserved replacement operations in MIR and excluded consumed replacement sources from implicit cleanup.
- Added interpreter/native parity and generated-C drop-order coverage.

## Epoch III — Filesystem capability acceptance checkpoint

- Added a project-level deterministic filesystem read/write acceptance application.
- Added interpreter/native parity coverage confined to test temporary directories.
- Added project audit assertions for allocation, filesystem-read, and filesystem-write policy classifications.
- Added project-derived negative tests for reads and writes outside their required capability regions.
- Updated the bootstrap environment to install declared development dependencies.
- Added an LF policy for executable shell scripts.

## Epoch II — Application Language

- Closed Application Foundation A and B into one application-language release.
- Added UTF-8 string literals and immutable `String` views.
- Added explicit `Allocator` values and `system_allocator()`.
- Added capability-gated `Buffer` allocation and string-to-buffer construction.
- Added owned byte-buffer mutation, length, indexed access, printing, and deterministic destruction.
- Added capability-gated native `file_read` runtime support.
- Extended move checking to owned buffers.
- Added automatic native cleanup for unreturned, non-explicitly-dropped buffers.
- Replaced inspection-only MIR with CFG-shaped blocks and branch/switch/goto/return terminators while retaining implicit-drop inspection compatibility.
- Added the multi-module text-pipeline acceptance application.
- Increased the test suite from 35 to 41 tests.

## Epoch III — Systems Core checkpoint

- Added immutable `ByteSlice` views over owned buffers.
- Added checked slice construction, length, and indexing.
- Added allocator-backed owned `I64Vec` collections.
- Added vector push, length, indexing, move checking, and deterministic destruction.
- Generalized owned-builtin cleanup beyond byte buffers.
- Added native C11 runtime support for slices and vectors.
- Added the multi-module binary packet acceptance project.
- Added systems-core ownership, type-checking, bounds, and native differential tests.
- Test suite increased from 41 to 45 tests.

## Epoch III — Generic Type Engine checkpoint

- Added source-level generic structs, enums, and functions.
- Added explicit monomorphization into nominal Merit declarations.
- Added scoped generic variant syntax (`Option<i64>::Some`).
- Added generic arity diagnostics.
- Added built-in `Copy`, `Eq`, `Ord`, and `Display` bound enforcement.
- Added generic `Option<T>` and `Result<T, E>` acceptance coverage.
- Added the `generic_result` project.
- Increased the regression suite from 45 to 50 tests.
