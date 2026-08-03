# Merit Codex Handoff

## Repository state
This repository contains the verified **Epoch III typed helper-dispatch checkpoint** of Merit.

Current baseline:
- 171 tests passing after editable installation
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
- user-defined destructors are absent
- returned/stored borrows are absent
- only the system allocator is implemented
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
