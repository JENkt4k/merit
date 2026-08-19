# Merit Programming Manual

This manual explains the **user-facing language**. It is intentionally different from the bootstrap/compiler documents: those describe how Merit is implemented; this manual describes how to write Merit programs.

The manual tracks the established `v0.1.0-alpha.1` language surface while `v0.1.0-alpha.2` replaces the compiler implementation. Replacement work must preserve these semantics rather than inventing a second language.

## Chapters

1. [Getting started](GETTING_STARTED.md) — program shape, modules, functions, projects, and the command line.
2. [Ownership and borrowing](OWNERSHIP.md) — moves, `borrow`, `borrow_mut`, `drop`, replacement, and deterministic cleanup.
3. [Traits and generics](TRAITS.md) — trait declarations, implementations, bounds, coherence, and explicit instantiation.
4. [Capabilities and contracts](CAPABILITIES_AND_CONTRACTS.md) — explicit authority, `with capability`, required capabilities, preconditions, and postconditions.

## Reading conventions

Examples marked **established** are part of the implemented alpha language. Deliberate exclusions are stated explicitly rather than approximated. In particular, stored references/lifetime parameters, trait objects, specialization, async, and concurrency are outside the current alpha.

The repository's executable examples are the best companion to this manual. Useful starting points include `examples/projects/trait_bounds`, `examples/projects/filesystem_capabilities`, `examples/projects/ledger_app`, and the ownership examples under `examples/`.

## Core design rule

Merit tries to make program meaning explicit and durable. Resource ownership, hazardous authority, numeric behavior, contracts, evaluation order, and ABI layout are language semantics rather than optimizer accidents. Compiler implementations may change; those guarantees should not.
