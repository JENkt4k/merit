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

HIR inspection exposes the concrete type-semantics table. MIR inspection exposes each function's owned locals, consumed roots, and explicit drops.

Semantic expression and statement nodes retain source spans in the program metadata table. Ownership state records move and drop origins, and MIR consumption metadata includes the originating span and source identity. Type, capability, replacement, exhaustiveness, constructor, field, and call diagnostics use the nearest actionable semantic node as their primary location.

Declaration objects and function records also retain spans. Declaration validation uses those locations for duplicate, unknown-type, numeric-policy, trait/implementation, and function capability diagnostics.

`SemanticNodeView` is the migration boundary around compact tuple nodes. It exposes typed kind/operand access together with primary and related spans. Checker, ownership effects, MIR control flow, interpreter execution, and C statement/type/expression lowering dispatch through this boundary while operands remain compatible during incremental accessor migration.

Named accessors now cover binding declarations, assignment/replacement targets and values, statement expressions, and explicit drops. Ownership-sensitive checker, analysis, interpreter, and C paths use these names rather than positional operands.

Call, generic-call, field, constructor, binary-expression, and control-flow accessors complete the initial named semantic surface. Call resolution and checker/interpreter/MIR branch handling use these accessors; compact operands remain as a transitional storage format.

Type/layout discovery, ownership path analysis, interpreter assignment, and C contract/cleanup/address helpers also dispatch through `Program.node()`. Direct raw tag reads are now confined outside semantic expression/statement dispatch, preparing the storage representation for typed variants.

Semantic statement consumers use named operands for declarations, `try`, assignment/replacement, capability regions, matching, branches, loops, returns, printing, and drops. Positional statement storage is now isolated behind `SemanticNodeView`.

Project assembly remaps spans from the merged semantic program to the owning source unit for unchanged source declarations. Project checking commands render structured compiler errors using those per-unit origins.

Generic extraction blanks template text while preserving its newlines. Monomorphized declarations carry a generated-line map back to the corresponding template lines and related instantiation lines. Project assembly remaps both locations to their owning units, so cross-module failures render the template as primary and the concrete application as a related note.

Errors raised before parsing completes, including generic arity and bound validation, are assigned expansion-time source spans. Merged-project loading remaps those spans before returning the structured compiler error.

## Planned decomposition

The next architectural slice moves AST/HIR/MIR structures into dedicated packages without changing semantics. Subsequent slices add enums and typed errors, buffers and allocators, then a real basic-block MIR.
