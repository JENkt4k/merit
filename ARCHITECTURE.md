# Merit Compiler Architecture

The prototype has entered repository-scale development. The current executable path is:

```text
Merit.toml
  → source discovery
  → module graph validation
  → per-file parse
  → symbol merge
  → semantic/ownership/capability checking
  → interpreter or C backend
  → native executable
```

## Current packages

- `merit.compiler`: established parser, semantics, interpreter, C backend, CLI
- `merit.project.manifest`: deterministic project configuration
- `merit.project.loader`: module graph and project assembly
- `merit.project.build`: project checking, interpretation, and native compilation
- `merit.project.cli`: project workflow
- `merit.diagnostics`: source-oriented diagnostic rendering

## Typed semantic metadata

After parsing and generic expansion, a cached type table classifies every concrete type by ownership, copyability, drop requirement, semantic kind, and drop strategy. A shared ownership-effects model derives consumed roots, explicit drops, and live owned locals for each function. The checker, MIR inspection, interpreter lifecycle model, and C cleanup lowering consume this metadata instead of independently reconstructing resource behavior.

Lexical resolution assigns a deterministic `BindingId` to every parameter, local, match payload, variable reference, and explicit drop. Ownership and flow state are keyed by these identities rather than source spelling. HIR/MIR expose the IDs, while generated C uses stable disambiguated names only when a source name is shadowed.

HIR inspection exposes the concrete type-semantics table. MIR inspection exposes each function's owned locals, consumed roots, and explicit drops.

Semantic expression and statement nodes embed typed `NodeProvenance` directly. Ownership state records move and drop origins, and MIR consumption metadata includes the originating span and source identity. Type, capability, replacement, exhaustiveness, constructor, field, and call diagnostics use the nearest actionable semantic node as their primary location.

Declaration objects and function records also retain spans. Declaration validation uses those locations for duplicate, unknown-type, numeric-policy, trait/implementation, and function capability diagnostics.

`SemanticNodeView` is the read-only typed dispatch facade over immutable per-kind `SemanticNode` storage. It exposes named operands together with primary and related provenance. Checker, ownership effects, MIR control flow, interpreter execution, project visibility, and C lowering dispatch through this boundary.

Named accessors now cover binding declarations, assignment/replacement targets and values, statement expressions, and explicit drops. Ownership-sensitive checker, analysis, interpreter, and C paths use these names rather than positional operands.

Call, generic-call, field, constructor, binary-expression, and control-flow accessors complete the named semantic surface. Call resolution and checker/interpreter/MIR branch handling use these accessors; indexed semantic-node compatibility has been removed.

Type/layout discovery, ownership path analysis, interpreter assignment, and C contract/cleanup/address helpers also dispatch through `Program.node()`. Direct raw tag reads are now confined outside semantic expression/statement dispatch, preparing the storage representation for typed variants.

Semantic statement consumers use named operands for declarations, `try`, assignment/replacement, capability regions, matching, branches, loops, returns, printing, and drops. Positional statement storage is now isolated behind `SemanticNodeView`.

Semantic expression consumers likewise use named atom, field, constructor, call, and binary operands. Recursive ownership and contract walkers traverse the view's typed operand collection.

The parser constructs immutable `SemanticNode` subclasses for every expression and statement. Public HIR/MIR inspection uses explicit serialization, and compiler consumers access nodes through named semantic views.

Concrete semantic storage is classified into atom, field, constructor, call, binary, binding, assignment, effect-statement, and control-flow families, with a distinct immutable runtime variant for every parser-produced semantic kind.

Ownership-sensitive binding/assignment/replacement statements and capability/branch/loop/match control flow now have distinct per-kind runtime variants beneath their shared storage families.

Atoms, struct initialization, direct/generic calls, and effect statements also have per-kind variants. Every semantic expression and statement produced by the parser is concrete and typed; no semantic node depends on tuple or indexed compatibility.

`NodeProvenance` groups primary and related locations, and `Program.provenance()` is the single lookup boundary used by semantic views and checker diagnostics. Semantic nodes, declarations, functions, parameters, fields, variants, traits, and implementations retain their own provenance.

Project assembly walks reachable semantic and declaration records after source-unit remapping and refreshes embedded primary/related locations in place. `Program` has no node-ID span maps or related-span maps.

`FunctionDecl` is now a typed record with explicit fields for its signature, effects, required capabilities, contracts, body, and provenance. Read-only mapping compatibility remains during consumer migration; HIR converts records through explicit serialization.

All internal function consumers now use typed fields. `FunctionDecl` exposes only read-only mapping compatibility for external inspection while generated declarations are changed through typed attributes.

HIR function bodies and MIR `semantic_blocks` serialize semantic nodes explicitly as JSON-safe kind/operand/provenance records. MIR no longer exposes internal tuple-compatible nodes.
Compiler semantic nodes use immutable typed storage with named semantic views and no indexed sequence compatibility; source provenance is attached only through controlled parser/project-loader paths.
Function and trait-method parameters share an immutable `Parameter` record consumed by checking, ownership, interpretation, C lowering, MIR, and project visibility.
Parser top-level output uses immutable `DeclarationEntry` records before assembling the typed `Program` symbol tables.
Parser field initializers and function effects/capability/contract clauses also use immutable typed intermediate records rather than positional tags.
Capability-gated filesystem builtins return nominal `FileReadResult` / `FileWriteResult` values with stable `FsError` categories in both interpreter and generated C.
Every concrete `Vec<T>` retains the allocator passed to `vec_new<T>`; generated growth and destruction dispatch through that stored allocator and include it in deterministic layout metadata.
`system_allocator()` and `portable_allocator()` provide distinct deterministic allocator identities while sharing the same checked vector lowering and ownership path.
Borrowed return modes are explicit semantic metadata. Origin and mutability are checked, ephemeral caller propagation is tracked, interpreter aliases preserve identity, generated C uses const-correct pointers, and the multi-module `borrowed_views` project plus shared-library tests verify the ABI. The first-alpha policy permits returned borrows only for field access/mutation, compatible borrow arguments, and validated borrowed-return relays; every storage and value-like escape is rejected. HIR/MIR publish the ephemeral-only policy. Stored reference values and general lifetime parameters remain deliberately unavailable.
Canonical MIR runs a reachability pass after CFG construction so blocks synthesized after terminal returns do not leak into inspection or later optimization inputs.
Exact literal/arithmetic/comparison conditions are folded to direct MIR gotos before reachability pruning, with the original condition retained in explicit inspection metadata.
Project builds can emit a PIC shared object and matching generated header from the same checked merged program used for executable builds.
Merged projects preserve `pub` exports so consumer headers expose public functions while generated implementation C retains private internal prototypes.
Project executable/shared builds use a content-addressed object cache for the merged generated-C translation unit, separating compilation from linking as the first step toward per-module objects.
Project preprocessing resolves explicit `module.symbol` qualification for imported public functions, types, and constructors while preserving source columns for downstream diagnostics.
Compiler diagnostics have a stable structured payload; both source and project CLIs can emit JSON containing codes, source ranges, excerpts, and related notes while retaining text output by default.
Custom struct destructors participate in shared lifecycle metadata. Interpreter and C cleanup invoke the custom body once before recursive field destruction; the accepted body subset excludes ownership-changing statements.

Generic application discovery records exact line/column ranges. Expansion errors use those ranges directly, and generated-node related provenance preserves the same application range through project remapping.

Diagnostic rendering consumes both start and end columns for primary and related spans, producing full-width source underlines rather than point-only carets.

Project assembly remaps spans from the merged semantic program to the owning source unit for unchanged source declarations. Project checking commands render structured compiler errors using those per-unit origins.

Generic extraction blanks template text while preserving its newlines. Monomorphized declarations carry a generated-line map back to the corresponding template lines and related instantiation lines. Project assembly remaps both locations to their owning units, so cross-module failures render the template as primary and the concrete application as a related note.

Errors raised before parsing completes, including generic arity and bound validation, are assigned expansion-time source spans. Merged-project loading remaps those spans before returning the structured compiler error.

## Ordered expression lowering

Native lowering recursively produces ordered prelude statements followed by one final C value. Every sibling operand or argument is materialized exactly once from left to right before the enclosing expression executes. Borrowed arguments materialize addresses rather than copying pointees, and loop-condition preludes remain inside the loop so they execute on every condition check. MIR inspection declares `expression_evaluation_order: left_to_right` at program and function scope.

## Planned decomposition

The semantic alpha blockers are now closed. Package decomposition and per-module object generation should preserve the established typed semantic pipeline rather than create parallel paths.

## Replacement compiler bootstrap

The active post-alpha path is a compiler written in the accepted Merit subset and initially compiled by the Python host. `spec/BOOTSTRAP.md` defines the versioned boundaries. The first slice, `examples/projects/bootstrap_lexer`, establishes typed byte-span tokens, explicit allocation, owned token-vector cleanup, and interpreter/native equivalence. It also exposed and closed aggregate initialization for functions returning monomorphized vectors in generated C.

Until stage equivalence is established, the Python compiler remains the executable semantic reference. Replacement stages must compare their outputs with it rather than silently creating a second language path.
