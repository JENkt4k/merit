# Merit Codex Handoff

## Repository state
This export contains the verified **Epoch III Generic Type Engine checkpoint** of Merit.

Baseline at export:
- 50 tests passing after editable installation
- Python-hosted compiler
- C11 native backend
- single-file and project CLIs
- interpreter/native differential verification

Verified command sequence:
```bash
python -m pip install -e . --no-build-isolation
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

## Architecture reality
The compiler is intentionally compact. Most implementation remains in `merit/compiler.py`; project loading and diagnostics are separate packages. Generic declarations are monomorphized into ordinary nominal declarations before the established semantic pipeline.

Current path:
```text
source/project
  -> parse
  -> generic discovery and monomorphization
  -> semantic/ownership/capability checking
  -> HIR/MIR inspection
  -> interpreter or C11 generation
  -> native executable
```

This design is useful because all instantiated generic code reuses one semantic source of truth. Preserve that property while gradually decomposing the compiler.

## Known constraints
- generic arguments are explicit
- generic definitions and uses are currently constrained by module handling
- nested generic applications are incomplete
- traits are compiler-defined bounds, not user declarations/implementations
- `I64Vec` is fixed-element rather than `Vec<T>`
- user-defined destructors are absent
- returned/stored borrows are absent
- only the system allocator is implemented
- modules merge into one generated C translation unit
- source spans are not retained through every IR node
- no LLVM backend, package registry, formatter, or LSP

## How to work safely
Make small commits inside a large subsystem. Keep the full suite green. Add compile-fail tests as aggressively as success tests. For each new construct, verify both interpreter behavior and generated-native behavior. Inspect generated C when mutations, borrows, returns, match subjects, or cleanup are involved.

## Files worth reading first
- `merit/compiler.py`
- `merit/project/loader.py`
- `tests/test_epoch_iii_generics.py`
- `tests/test_epoch_iii_systems_core.py`
- `examples/projects/generic_result/`
- `examples/projects/binary_packet/`
- `spec/OWNERSHIP.md`
- `spec/NUMERICS.md`
