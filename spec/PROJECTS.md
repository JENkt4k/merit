# Merit Project and Module Model — Application Foundation A

## Shared-library builds

`merit-project build-shared <Merit.toml> -o <output>` checks and lowers the same merged project used by executable builds, emits adjacent `.c` and `.h` files, and compiles a position-independent `.so`. Non-`main` Merit functions use their generated `merit_<name>` C symbols and header declarations.

The current acceptance gate loads the resulting library from a C-compatible foreign caller and invokes a primitive `i32 -> i32` function. Consumer headers include public project functions and omit private helpers; platform-specific library suffixes and richer ABI surface policy remain future hardening work.

## Manifest

A project is rooted by `Merit.toml`.

```toml
[package]
name = "ledger_app"
entry = "src/main.mrt"
sources = ["src/**/*.mrt"]

[build]
c_flags = ["-O2"]
```

The manifest is deterministic: source discovery uses explicit globs, the entry source is mandatory, and compiler flags are part of the build input.

## Modules

Every source file declares exactly one module. Imports are explicit:

```text
module ledger_main
import ledger_types;
import ledger_operations;
```

Application Foundation A deliberately uses a flat global symbol namespace after module-graph validation. Qualified names and visibility are reserved for the next slice. This keeps the implementation honest while allowing real multi-file native programs now.

## Validation

The loader rejects:

- missing imports
- import cycles
- duplicate module names
- duplicate functions
- duplicate types
- `main` outside the entry module

## Compilation

All validated units are merged into one typed program before existing semantic, ownership, contract, capability, interpreter, and C-backend passes execute. Separate object compilation is a later milestone.
