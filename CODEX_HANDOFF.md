# Merit Codex Handoff

## Repository state
This repository contains the verified **Epoch III user-defined destructor checkpoint** of Merit.

Current baseline:
- 289 tests passing after editable installation
- Python-hosted compiler
- C11 native backend
- single-file and project CLIs
- interpreter/native differential verification

Verified command sequence:
```bash
python -m pip install -e ".[dev]" --no-build-isolation
python -m pytest -q
```

## Implemented language surface
- exact fixed-scale decimals and explicit rounding
- bounded and checked integer operations
- stable-layout structs and C headers
- contracts and capability auditing
- ownership, moves, borrows, explicit and implicit drops
- control flow and CFG-shaped MIR inspection
- payload enums, exhaustive matching, and typed `try`
- multi-module projects and visibility
- UTF-8 string views, owned byte buffers, byte slices
- explicit system allocator and allocator-backed `I64Vec`
- generic structs, enums, and functions
- explicit generic arguments and monomorphization
- compiler-defined `Copy`, `Eq`, `Ord`, and `Display` bounds
- nominally scoped generic enum variants
- user-declared traits, coherent implementations, and project-wide trait-bound dispatch
- allocator-backed generic `Vec<T>` collections with owned-element drop glue
- project-level filesystem read/write capability parity and audit coverage
- explicit owned replacement for locals, fields, mutable borrows, and vector elements
- shared typed lifecycle metadata and function ownership effects across checker, MIR, interpreter, and C cleanup
- source-aware move/drop state with primary diagnostics, origin notes, and MIR consumption locations
- source-mapped structured semantic errors across single-source and multi-module project workflows
- actionable primary spans for type, capability, replacement, exhaustiveness, constructor, field, and call diagnostics
- original-template semantic spans for locally monomorphized generic bodies without shifting following declarations
- cross-module generic diagnostics linking template errors to instantiation sites with per-file excerpts
- precise declaration spans for type, trait, implementation, field, function, and declaration-policy errors
- source-aware generic arity, bound, and ambiguous-dispatch expansion errors across single files and projects
- typed semantic-node views used by checking and shared ownership analysis over the backend-compatible tuple representation
- typed node dispatch across MIR, interpreter, and native C lowering with unchanged parity
- named typed operands for ownership-sensitive initialization, assignment, replacement, return, and drop paths
- typed call, constructor, field, binary-expression, and control-flow accessors used by semantic and runtime paths
- typed dispatch throughout semantic helper paths with no direct tuple-tag reads for expressions or statements
- named statement operands across checker, ownership, MIR, interpreter, and C lowering
- named expression operands across ownership, checking, interpretation, and C lowering with no direct positional reads
- concrete tuple-compatible semantic node storage produced uniformly by the parser
- typed storage families for atoms, calls, constructors, bindings, replacement, effects, and control flow
- distinct ownership-sensitive and control-flow node variants with compatibility serialization
- concrete per-kind runtime variants for every parser-produced semantic expression and statement
- centralized typed primary/related provenance lookup for node views and checker diagnostics
- exact generic application columns for expansion errors and related instantiation notes
- full-width primary and related source underlines from semantic span ranges
- embedded primary/related provenance on every semantic node with project remapping parity
- direct project remapping of embedded semantic provenance without duplicate ID-map entries
- embedded declaration/function provenance with external node-ID maps removed
- typed function declaration fields with mapping compatibility and explicit HIR serialization
- typed function-field consumers across semantics, interpreter, C lowering, MIR, and project loading
- JSON-safe semantic kind/operand/provenance serialization in HIR and MIR inspection
- Canonical explicit MIR output with no raw tuple-compatible block surface
- Immutable typed semantic storage with controlled provenance attachment
- Named semantic access throughout compiler/project consumers with no indexed node compatibility
- Typed `SemanticNode` and `MatchArm` records with explicit inspection serialization
- Typed `Parameter` records across semantic, ownership, interpreter, native, MIR, and project paths
- Typed parser declaration records through symbol-table assembly
- Typed field-initializer and function-clause parser records
- Typed filesystem results with interpreter/native OS-failure parity
- Allocator-retaining `Vec<T>` growth/drop paths with deterministic layout assertions
- System and portable allocator providers verified through one interpreter/native vector path
- Explicit allocator compatibility policy for future zero-copy collection transfers
- Zero-copy `vec_transfer<T>` with allocator, alias, emptiness, and owned-drop safety
- Vector allocator introspection for transfer compatibility preflight
- Dependency-ordered nested vectors with recursive owned cleanup
- Allocator-retaining buffers and filesystem-read provider propagation
- Allocator-retaining legacy `I64Vec` runtime parity
- Allocation capability gating and audit coverage for every growable-container push
- Multi-capability filesystem reads with separate I/O and allocation hazards
- Symmetric filesystem-write allocation authority and audit coverage
- Explicit borrowed-return modes with caller-origin propagation and interpreter/native pointer parity
- Mutable borrowed-result field assignment and owned replacement
- Multi-module `borrowed_views` acceptance project for public shared/mutable views
- Stable shared-library pointer ABI for public borrowed-return functions
- Const-correct C signatures for shared borrow parameters and results
- Borrow-aware postcondition result lowering
- Platform-aware shared-library suffix, linker, and PIC policy
- Definite-return analysis for non-void control-flow paths
- Checked, truncating signed integer division with deterministic failure parity
- Type-specific checked primitive, bounded, and decimal operator lowering
- Numeric-only operator domains and destination-independent comparison lowering
- Numeric-only explicit checked arithmetic built-ins
- Destination-typed interpreter expressions with exactly-once target evaluation
- Exactly-once side-effecting replacement targets in interpreter and native C
- Deterministic value-before-target evaluation for copy assignments in generated C
- Side-effect-free pre/postcondition calls with mutating and hazardous operations rejected
- Trap-aware MIR constant folding for arithmetic conditions
- Canonical MIR reachability pruning after CFG construction
- Exact constant-condition MIR folding with dead-branch pruning
- PIC C shared-library builds with generated headers and foreign-caller acceptance
- Public-only project consumer headers with private internal C prototypes retained
- Stable-layout struct foreign-call acceptance through the generated shared library
- Public ABI type-closure validation and private type filtering
- Content-addressed merged-project object caching with separate linking
- Explicit qualified imports for functions, types, and constructors
- Stable JSON diagnostics from compiler/project CLIs with related source notes
- Stable project-system diagnostic codes and qualified-import source ranges
- Atomic object-cache publication with failed-compilation cleanup
- Custom struct destructors with exact-once interpreter/native cleanup parity
- Cross-module destructor visibility and source-mapped project diagnostics
- Structured destructor control flow and copy-field mutation
- Strict numeric-literal compatibility and range validation at every value boundary

## Architecture reality
The compiler is intentionally compact. Most implementation remains in `merit/compiler.py`; project loading and diagnostics are separate packages. Generic declarations are monomorphized into ordinary nominal declarations before the established semantic pipeline.

Current path:
```text
source/project
  -> parse
  -> generic discovery and monomorphization
  -> concrete type table and ownership effects
  -> semantic/ownership/capability checking
  -> HIR/MIR inspection
  -> interpreter or C11 generation
  -> native executable
```

This design is useful because all instantiated generic code reuses one semantic source of truth. Preserve that property while gradually decomposing the compiler.

## Known constraints
- generic arguments remain explicit
- no associated types, blanket impls, specialization, trait objects, or dynamic dispatch
- trait methods cannot yet declare effects or required capabilities
- user-defined destructors support effect-free structured bodies; ownership/capability-changing destructor contracts remain deferred
- returned borrows are ephemeral; reference-typed local storage and general lifetime parameters are absent
- system and portable allocator identities are implemented over the same host allocation primitives
- modules merge into one generated C translation unit
- ownership and project-unit spans are retained, but broader semantic nodes and generic rewrites still need source maps
- no LLVM backend, package registry, formatter, or LSP

## How to work safely
Use cohesive epic commits with intermediate green test gates. Add compile-fail tests as aggressively as success tests. For each new construct, verify both interpreter behavior and generated-native behavior. Inspect generated C when mutations, borrows, returns, match subjects, or cleanup are involved.

## Files worth reading first
- `merit/compiler.py`
- `merit/project/loader.py`
- `tests/test_epoch_iii_generics.py`
- `tests/test_epoch_iii_systems_core.py`
- `examples/projects/generic_result/`
- `examples/projects/binary_packet/`
- `spec/OWNERSHIP.md`
- `spec/NUMERICS.md`
