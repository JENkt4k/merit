# Merit Project and Module Model — Application Foundation A

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
