# Merit Project and Module Model — Application Foundation A

## Shared-library builds

`merit-project build-shared <Merit.toml> -o <output>` checks and lowers the same merged project used by executable builds, emits adjacent `.c` and `.h` files, and compiles a position-independent `.so`. Non-`main` Merit functions use their generated `merit_<name>` C symbols and header declarations.

The current acceptance gate loads the resulting library from a C-compatible foreign caller and invokes both a primitive `i32 -> i32` function and a stable-layout struct passed by value. Consumer headers include public project functions and omit private helpers; platform-specific library suffixes remain future hardening work.

Public ABI signatures are closed over public types: exported functions, structs, and enums cannot expose a private project type. Consumer headers omit private structs and enums while retaining public types imported from another project module.

## Object caching

Executable and shared builds compile generated C to a content-addressed object before linking. The cache key includes generated source, resolved compiler binary identity, project C flags, and PIC mode. Identical rebuilds reuse the existing object, while flag or compiler changes produce a distinct entry. This checkpoint caches the current merged project translation unit; per-module object generation remains future work.

Object publication is atomic: compilation targets a cache-local temporary file, which replaces the final cache entry only after successful compiler exit. Failed compilation removes the temporary file and publishes no object.

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

Project symbols retain explicit visibility while lowering through the current merged semantic program. Imported public functions, types, and constructors may use `module.symbol` qualification; qualification does not replace the requirement for an explicit import and preserves source columns during preprocessing.

## Validation

The loader rejects:

- missing imports
- import cycles
- duplicate module names
- duplicate functions
- duplicate types
- `main` outside the entry module

## Compilation

All validated units are merged into one typed program before existing semantic, ownership, contract, capability, interpreter, and C-backend passes execute. The merged generated-C translation unit uses content-addressed object caching; per-module object compilation is a later milestone.

## First-alpha ledger acceptance

`examples/projects/ledger_app` is the substantial `v0.1.0-alpha.1` application gate. Five modules combine exact `USD`, bounded account IDs, typed ledger results, contract-checked mutation, explicit buffer allocation, capability-gated audit-file output, and a stable public `Account` ABI. The gate verifies interpreter/native output and filesystem contents, audits allocation/write hazards, inspects generated sequencing and layout assertions, and calls exact-decimal exports through a foreign C-compatible caller.
