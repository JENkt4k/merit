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

Project assembly remaps spans from the merged semantic program to the owning source unit for unchanged source declarations. Project checking commands render structured compiler errors using those per-unit origins.

Generic extraction blanks template text while preserving its newlines. Monomorphized declarations carry a generated-line map back to the corresponding template lines and related instantiation lines. Project assembly remaps both locations to their owning units, so cross-module failures render the template as primary and the concrete application as a related note.

## Planned decomposition

The next architectural slice moves AST/HIR/MIR structures into dedicated packages without changing semantics. Subsequent slices add enums and typed errors, buffers and allocators, then a real basic-block MIR.
