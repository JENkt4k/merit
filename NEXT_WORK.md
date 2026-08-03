# Next Work - Roadmap Status

## Goal
Advance the core Merit feature set in complete, testable epic slices while preserving interpreter/native parity.

## Original epic status
- Project-wide generic expansion and trait evidence: substantial checkpoint complete.
- Contracts and verification depth: active checkpoint complete in this slice.
- Capability model hardening: active checkpoint complete in this slice.
- Memory model polish: active checkpoint complete in this slice.
- Project-level filesystem capability acceptance: complete in this slice.

## Filesystem capability acceptance checkpoint now available
- A dedicated project writes and reads deterministic `MRT` bytes through `file_write` and `file_read`.
- Acceptance execution is confined to pytest or shell-created temporary directories.
- Interpreter and native output agree for project-level filesystem operations.
- Project audit output classifies allocation, filesystem reads, and filesystem writes with their review categories and lexical scope.
- Project-derived negative tests reject read and write calls outside the corresponding capability region.

## Trait checkpoint now available
- User-declared traits with method signatures.
- `impl Trait for Type` blocks.
- Coherence rule: at most one implementation for a concrete trait/type pair within the program.
- Generic bounds resolved through user impls for concrete instantiations.
- Trait method calls inside instantiated generic functions lower to concrete impl methods.
- Project-wide generic expansion supports templates, instantiation sites, and trait impl evidence split across imported modules.
- Project visibility checks cover generic template ownership, generic bounds, trait method signatures, and impl trait/target references.
- Interpreter/native verification through `examples/projects/trait_bounds`.

## Trait limits deliberately retained for the compact compiler
- No associated types, blanket impls, specialization, trait objects, or dynamic dispatch.
- Trait method signatures cannot yet express effects or required capabilities; impl methods using them are rejected.
- Trait-method lowering is still monomorphization-time source rewriting, guarded by ambiguity tests, not final AST-aware lowering.
- Project-wide generic expansion is still compact source-level monomorphization, not a final typed generic IR or incremental compilation model.

## Collection checkpoint now available
- `Vec<i64>` type syntax expands through the existing monomorphization path.
- `Vec<Pair<i64,i32>>` stores generic structs by value.
- `Vec<Buffer>` moves owned buffers into the vector and destroys live elements on vector drop.
- Structs containing owned fields move their field sources and generate deterministic aggregate drop glue.
- Enums containing owned payloads move constructor payload sources and generate active-variant drop glue.
- Generic `Option<Vec<i64>>` and `Result<Vec<i64>, Error>` compile, execute, and verify natively.
- `Vec<OwnedStruct>` supports structs with owned fields through pop/drop semantics and generated element destructors.
- Generated C marks expected unused helpers and match bindings so project verification output stays signal-focused.
- Generated headers emit static layout assertions for every concrete `Vec<T>`.
- Generated headers emit conservative static layout assertions for enum tag and payload placement.
- `merit layout` and `merit-project layout` report layout hashes for stable structs, generated vectors, and enums.
- Generated headers include layout hash identity comments for stable structs, generated vectors, and enums.
- Generic-style vector intrinsic calls such as `vec_new<i64>` and `vec_pop<OwnedText>` parse as typed `generic_call` nodes and resolve through semantic call handling.
- Vector acceptance tests and the generic collections example use generic-style vector intrinsic calls instead of concrete `vec_*__T` spelling.
- Vector intrinsic arity, return kind, receiver mode, allocation requirement, and owned-copy restrictions are centralized in one compiler table.
- Type ownership, drop requirement, and copyability are classified through shared semantic helpers used by checker, cleanup, MIR, and generated drop emission paths.
- `vec_new__T`, `vec_push__T`, `vec_len__T`, `vec_get__T`, `vec_set__T`, `vec_pop__T`, and `vec_drop__T` are available for concrete `T`.
- `vec_get__Buffer` is rejected because it would copy an owned element; `vec_pop__Buffer` is the move-out operation.
- Vectors are owned values: copying/move-after-use is rejected.
- Allocation requires the `allocate` capability.
- `merit audit` and `merit-project audit` report declared capabilities, capability policy requirements, capability sites, capability-bearing calls, and hazardous builtin/vector operations.
- Generated C marks capability regions with explicit begin/end audit comments.
- Mutation requires a mutable vector binding.
- Interpreter/native verification through `examples/projects/generic_collections`.

## Contract checkpoint now available
- `requires` and `ensures` expressions are type-checked as boolean/comparison contract conditions before execution/codegen.
- `old()` is legal only while checking postconditions.
- `old()` in preconditions and ordinary code is rejected during checking instead of surfacing later.
- Interpreter and generated native binaries agree on deterministic precondition failure behavior.
- Interpreter and generated native binaries agree on deterministic postcondition failure behavior.
- Native contract failures preserve distinct exit codes for precondition and postcondition failures.

## Capability checkpoint now available
- Builtin hazardous operation metadata covers allocation, filesystem read, and filesystem write classes.
- `file_write` is a distinct capability-gated hazardous operation.
- Unauthorized filesystem writes are rejected during checking.
- Authorized filesystem writes execute in both interpreter and generated native binaries.
- Audit output includes centralized capability policy metadata: hazard class, review category, and lexical scope.
- Audit requirements and observed hazardous operations carry consistent policy classifications.

## Memory model checkpoint now available
- Owned-source consumption is centralized across bindings, assignments, returns, struct construction, enum construction, vector value operations, builtin calls, and user-function calls.
- Moving an owned field out of an aggregate is rejected until partial-move/drop-state tracking exists.
- Passing an owned field to a consuming function is rejected.
- Returning an owned field from an aggregate is rejected.
- Constructing a new aggregate by moving an owned field out of another aggregate is rejected.
- Plain assignment into existing owned storage remains rejected so replacement is always explicit.
- Explicit `replace(target, replacement)` supports mutable owned locals, owned fields, and mutable borrowed storage.
- Explicit `vec_replace<T>` supports checked replacement of owned vector elements.

## Typed semantic metadata checkpoint now available
- A cached type table classifies ownership, copyability, drop requirements, semantic kinds, and backend-neutral drop strategies.
- Vector get/set/replace restrictions use one declarative element policy plus concrete type metadata.
- A shared ownership-effects model derives owned locals, consumed roots, and explicit drops per function.
- MIR and native cleanup consume the same function ownership effects.
- Direct owned local moves no longer leave a duplicate native epilogue drop.
- HIR reports concrete type semantics; MIR reports consumed roots and explicit drops.
- The interpreter recursively models destruction through the same lifecycle metadata.

## Source-aware ownership diagnostic checkpoint now available
- Variable, field, and drop nodes retain source spans and source identity after parsing.
- Move and drop state carries origin spans through branches and loops.
- Use-after-move and use-after-drop errors identify the later invalid use and the earlier consumption site.
- Rendered source diagnostics show both primary and note excerpts.
- Shared ownership effects and MIR expose consumption source locations.
- Generic expansion currently reports locations in expanded source when rewriting changes line structure; typed source maps remain future work.

## Project semantic diagnostic checkpoint now available
- Merged project nodes map back to their owning source unit and original line numbers.
- `merit-project check`, build, run, verify, and audit render structured semantic errors consistently.
- Multi-module ownership failures identify the correct non-entry source file.
- The single-source CLI uses the same structured semantic renderer.

## Broad semantic span checkpoint now available
- Literals, constructors, calls, arithmetic, declarations, assignments, replacement, returns, capability regions, and control-flow nodes retain spans.
- Type, capability, replacement, match-exhaustiveness, constructor, field, and call diagnostics select actionable primary locations.
- Regression tests verify rendered file, line, and source excerpts for the principal semantic diagnostic families.

## Local generic source-map checkpoint now available
- Generic template removal preserves the original line structure of following declarations.
- Generated monomorphized bodies map semantic nodes back to their original template lines.
- Single-source diagnostics inside instantiated functions render the original template excerpt.

## Cross-project generic provenance checkpoint now available
- Generated semantic nodes retain their concrete generic instantiation line as related provenance.
- Merged projects remap both template and instantiation spans to their owning source units.
- Diagnostic notes load excerpts from their own source files rather than reusing primary-source text.
- Project source preprocessing preserves line numbers while removing module and import declarations.

## Declaration diagnostic checkpoint now available
- Enum, variant, trait, trait-method, implementation, decimal, bounded, struct, field, and function declarations retain spans.
- Duplicate symbols and members, unknown declaration types, invalid numeric declarations, trait/implementation errors, and function capability errors point to their declarations.
- Compile errors raised during AST transformation are unwrapped for consistent structured rendering.

## Generic expansion diagnostic checkpoint now available
- Generic arity and trait-bound failures point to the concrete application line.
- Expansion errors retain structured spans through merged-project loading and remap to the calling unit.
- Ambiguous trait-method expansion can report the template as primary with the instantiation as a related location.

## Typed semantic-node adapter checkpoint now available
- `SemanticNodeView` provides typed kind, operands, primary span, and related provenance over compatibility tuples.
- `Program.node()` is the centralized boundary from legacy representation to semantic-node metadata.
- The checker and shared ownership-effects analysis dispatch through the typed view.
- MIR, interpreter, and C lowering dispatch through the same typed view while retaining compatibility operands.

## Typed backend-dispatch checkpoint now available
- MIR control-flow lowering uses semantic node kinds rather than raw positional tag dispatch.
- Interpreter statement and expression execution uses the typed node boundary.
- C statement, expression-type, and expression lowering uses the typed node boundary.
- Tuple operands remain temporarily compatible while typed ownership-sensitive accessors are introduced.

## Ownership-sensitive node accessor checkpoint now available
- Typed accessors cover binding names/types/initializers, assignment and replacement targets/values, and statement expressions.
- Checker and ownership analysis use named operands for ownership-sensitive operations.
- Interpreter and C lowering use the same accessors for initialization, replacement ordering, returns, printing, and drops.
- Accessor tests cover source provenance, owned initialization, and replacement operands.

## Call and control-flow accessor checkpoint now available
- Typed accessors cover calls, generic type arguments, fields, constructors, binary operands, conditions, branches, nested bodies, and match arms.
- Call resolution uses the typed view for both ordinary and generic intrinsic calls.
- Checker, interpreter, and MIR control-flow paths use named branch and match operands.

## Typed helper-dispatch checkpoint now available
- Type discovery and layout collection use typed declaration accessors.
- Ownership path/root helpers and interpreter assignment use typed field/variable dispatch.
- C contract scanning, cleanup discovery, statement walking, and address lowering use the typed boundary.
- Compiler semantic statement/expression tag dispatch no longer relies on direct positional tag reads.

## Typed statement-operand checkpoint now available
- Named accessors cover mutability, capability names/regions, `try` bindings, match subjects/arms, and branch/loop bodies.
- Checker, ownership analysis, interpreter, MIR, and C lowering no longer read semantic statement operands positionally.
- Replacement evaluation and drop ordering remain unchanged across interpreter/native paths.

## Typed expression-operand checkpoint now available
- Named accessors cover atom values, fields, constructors, calls, generic calls, and binary expressions.
- Ownership analysis, checker, interpreter, and C lowering no longer read semantic expression operands positionally.
- Recursive expression walkers traverse the typed operand collection.

## Concrete semantic storage checkpoint now available
- The parser creates `SemanticTuple` storage for every semantic expression and statement.
- Semantic nodes are distinguishable from incidental tuples while retaining equality/index compatibility during migration.
- `SemanticNodeView` remains the typed accessor and provenance facade over concrete storage.

## Typed semantic storage-family checkpoint now available
- Concrete nodes are classified as atom, field, constructor, call, binary, binding, assignment, effect-statement, or control-flow storage.
- Parser construction selects the storage family deterministically by semantic kind.
- Storage-family tests cover capability control flow, owned bindings/calls, and replacement nodes.

## Safety-critical per-kind variant checkpoint now available
- `LetNode`, `TryLetNode`, `AssignNode`, and `ReplaceNode` distinguish ownership-sensitive statements.
- `CapabilityNode`, `IfNode`, `WhileNode`, and `MatchNode` distinguish control-flow invariants.
- Per-kind variants retain family inheritance and tuple-compatible serialization.

## Complete per-kind semantic variant checkpoint now available
- Atom kinds have distinct string, number, and variable variants.
- Construction and invocation distinguish struct initialization, direct calls, and generic calls.
- Return, print, expression-statement, and drop effects have distinct variants.
- Every parser-produced semantic expression and statement now has a concrete per-kind runtime type.

## Typed provenance boundary now available
- `NodeProvenance` groups primary and related spans behind one typed value.
- `Program.provenance()` is the only semantic lookup boundary used by node views and checker diagnostics.
- Existing project remapping remains compatible while embedded storage is implemented next.

## Column-precise generic provenance now available
- Generic application discovery records start and end columns as well as source lines.
- Expansion-time arity/bound failures underline the concrete application.
- Generated-body related notes underline the instantiation in both single-source and project diagnostics.
- The diagnostic renderer uses span end columns to underline full primary and related ranges.

## Embedded semantic-node provenance checkpoint now available
- Every `SemanticTuple` carries typed primary and related `NodeProvenance` directly.
- `Program.provenance()` prefers embedded locations and falls back to legacy declaration maps.
- Project merging refreshes embedded provenance after remapping both locations to owning units.
- Semantic-node diagnostics remain source-aware after legacy maps are cleared.

## Semantic provenance map-retirement checkpoint now available
- Semantic nodes no longer duplicate primary or related locations in external ID maps.
- Project merging remaps embedded semantic provenance directly.
- External maps now contain only declaration/function records awaiting embedded provenance.

## Fully embedded provenance checkpoint now available
- Declaration dataclasses and `FunctionDecl` records carry typed provenance directly.
- Duplicate-symbol and declaration diagnostics use embedded locations.
- Project assembly remaps semantic and declaration provenance in place.
- `Program.spans` and `Program.related_spans` have been removed.

## Typed function declaration checkpoint now available
- `FunctionDecl` is a typed record with explicit signature, effect, capability, contract, body, and provenance fields.
- Mapping compatibility keeps existing semantic/backend consumers stable during field migration.
- HIR serializes function records explicitly instead of exposing internal objects.

## Typed function consumer checkpoint now available
- Type discovery, ownership analysis, checking, interpretation, C lowering, MIR, and project loading use typed function fields.
- Read-only mapping access remains solely as a compatibility surface for external inspection/tests.
- Generated implementation functions mutate typed fields rather than mapping keys.

## Explicit semantic serialization checkpoint now available
- HIR function bodies serialize semantic nodes as JSON-safe kind/operand/provenance records.
- MIR exposes `semantic_blocks` with the same explicit representation alongside compatibility blocks.
- Primary and related source locations are included without exposing internal node objects.

## Recommended next epic
Continue typed semantic-node decomposition:
- Migrate MIR inspection tests/tooling to `semantic_blocks` and retire raw compatibility blocks.
- Replace tuple-compatible semantic storage with immutable typed sequence records.
- Remove tuple compatibility only after every operand access is typed.

## Deliberately deferred
- specialization
- associated types
- higher-kinded types
- blanket implementations unless coherence is formally defined
- trait objects/dynamic dispatch
- implicit generic type inference
- concurrency

## Suggested implementation order
1. Migrate MIR consumers to explicit semantic serialization.
2. Replace tuple-compatible storage with immutable typed records.
3. Continue replacing compact tuple-AST special cases with typed nodes.

## Acceptance gates
The checkpoint is complete only when all of these pass:

### Positive
- owned locals, fields, and mutable borrows can be replaced explicitly.
- owned vector elements can be replaced with checked indexing.
- interpreter and native replacement behavior agree.
- `Vec<i64>` grows and preserves values.
- `Vec<Pair<i64,i32>>` stores generic structs.
- `Vec<Buffer>` moves owned buffers into the vector and destroys each live element exactly once.
- structs with owned fields move sources into the struct and drop owned fields exactly once.
- enums with owned payloads move sources into active variants and drop active payloads exactly once.
- vectors of structs with owned fields drop all live elements exactly once.
- trait-bounds acceptance project remains green.
- generic `Option<Vec<i64>>` and `Result<Vec<i64>, Error>` compile and execute.
- interpreter and native output match for all acceptance programs.

### Negative
- duplicate trait impl remains rejected.
- missing trait impl remains rejected at generic instantiation.
- pushing an owned value and then using the moved source rejected.
- copying an owned vector element with `vec_get__Buffer` rejected.
- using an owned source after moving it into a struct field rejected.
- using an owned source after moving it into an enum payload rejected.
- using an owned enum subject after match rejected.
- copying an owned struct element with `vec_get__OwnedText` rejected.
- copying `Vec<T>` rejected.
- use-after-drop rejected.
- immutable vector mutation rejected.
- capability-free allocation rejected.
- hazardous builtin and vector operations appear in source/project audit output.

### Regression
- all existing tests remain green.
- simple examples, text pipeline, binary packet, generic result, trait bounds, and generic collections projects still verify natively without expected helper-warning noise.
- generated `Vec<T>` headers assert pointer/length/capacity layout at C compile time.
- generated enum headers assert tag offset and payload placement at C compile time.
- source and project layout commands report hashes for generated vectors and enums.
- contract precondition failures produce matching interpreter/native diagnostics.
- contract postcondition failures produce matching interpreter/native diagnostics.
- invalid contract expression types are rejected during checking.
- `old()` outside postconditions is rejected during checking.
- unauthorized `file_write` calls are rejected during checking.
- authorized `file_write` calls match in interpreter and native execution.
- audit output classifies allocation, filesystem read, and filesystem write hazards.
- owned field extraction into a new binding is rejected.
- owned field extraction into a consuming call is rejected.
- owned field extraction through aggregate construction or return is rejected.
- plain assignment into owned storage remains rejected in favor of explicit replacement.
- replacement sources are consumed and aliasing replacement expressions are rejected.

## Recommended acceptance project
Create `examples/projects/generic_collections/` with modules for:
- domain types
- trait implementations
- generic vector operations
- entry point

Expected demonstration:
- allocate a `Vec<Buffer>`
- insert multiple owned strings
- pop an owned string back out
- inspect owned data before explicit drop
- wrap owned data in a struct and drop the aggregate
- move vectors through `Option` and `Result` payloads
- store owned structs in vectors and move them back out with `pop`
- destroy all resources exactly once
