# Core HIR to MIR lowering

`merit.bootstrap.hir_to_mir` is the first executable bridge between
`bootstrap-hir-v1` and `bootstrap-mir-v1`.

## Purpose

The bridge proves that the two versioned contracts can support deterministic
lowering without allowing the C backend to rediscover source-language
semantics. It is intentionally a strict core, not a complete alpha compiler.

## Supported HIR

The initial lowerer accepts function roots containing:

- literals and resolved identifiers
- exact, checked, wrapping, saturating, or floating binary operations
- explicit conversions
- resolved calls and constructors
- `let` and assignment operations
- moves and borrows
- explicit drops
- contract checks
- capability scopes
- returns

Every produced MIR function has one explicit entry block, ordered instruction
IDs, deterministic local allocation, and an explicit return terminator.

## Identity mapping

HIR binding IDs are sorted and mapped to MIR locals before temporaries are
allocated. Each binding-backed local retains `source_binding_id`, allowing
parity tools to verify that shadowed names and ownership state remain attached
to semantic identities rather than source spelling.

Temporary locals are allocated in deterministic HIR postorder and named from
the source node ID. The names are diagnostic aids; canonical IDs define the
interchange identity.

## Preserved semantics

The lowerer copies these policies into MIR rather than interpreting them:

- numeric policy for binary operations
- conversion policy for conversions
- ownership mode for values, moves, borrows, and drops
- contract kind for checks
- capability requirements for scopes and functions
- source spans for instructions and terminators

## Rejection policy

Unsupported or malformed checked HIR raises `HirToMirError` with deterministic
messages. The lowerer does not approximate `if`, `while`, `match`, aggregate
field operations, allocation, or multi-block control flow yet.

This rejection boundary is deliberate. Adding a HIR node to the accepted set
requires a corresponding MIR representation and tests; the implementation may
not silently lower an unsupported construct through backend-specific behavior.

## Next slices

1. multi-block lowering for `if`, `while`, and `match`
2. field load/store and aggregate construction details
3. explicit allocation/deallocation lowering
4. exact-once cleanup insertion and verification
5. canonical HIR/MIR observations through the shared parity engine
6. deterministic C emission consuming MIR only
