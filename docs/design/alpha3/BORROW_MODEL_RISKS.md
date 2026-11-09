# Borrow-model risks and reversibility

**Status:** Design-only analysis. Evidence IDs refer to `BORROW_MODEL_EVIDENCE.md`.

| Risk | A inferred spans | B lexical spans | F separated authority | Mitigation/evidence needed |
| --- | --- | --- | --- | --- |
| Dangling local reference after move/drop/replace | Requires path-sensitive use and origin proof. | Lexical scope prevents some safe moves but still needs origin proof. | Must keep validity distinct from access permission; use A or B solver. | Cases 06–09, 17, 22, 28; edge cleanup traces [E09–E12]. |
| Conflicting aliases | Needs place overlap and live-use spans. | Needs place overlap within lexical interval. | Same under fixed alias policy; richer policy needs new semantics. | Cases 02–05, 20–21, 27; reject unknown overlap. |
| Joins, loops, error edges | Fixed-point and conservative union; risk of false acceptance if a path is missed. | Less liveness precision, but still must prove origin and cleanup per edge. | Solver-dependent; decomposition itself proves nothing. | Cases 12–17; later bounded solver prototype [E12–E13]. |
| Alpha.2 compatibility | New local syntax and diagnostics must not reinterpret old modes. | Same. | Same; avoid adding new meaning to old discriminants. | Run existing accepted/rejected corpus and byte-stable artifacts [E01, E06–E08]. |
| Python/production divergence | Two independent semantic paths need parallel rules and differential evidence. | Same, with simpler interval policy. | Same; avoid Python production fallback. | Reference/native/stage differential tests [E02–E07]. |
| Cost and annotations | Static analysis cost unknown; no runtime cost required. | Lower apparent solver burden; rejects more useful code. | No inherent runtime cost under current definition. | Measure compiler wall time, peak RSS, artifact size, annotation count; no invented scores [E13]. |

## Public commitments versus reversible internals

Public commitments: reference validity, access conflict policy, scope/escape
rules, required accepted programs, cleanup order, failure diagnostics at the
contract level, and any new syntax or ABI. Once released, changing accepted
program behavior or rejecting previously accepted programs is expensive.
Internal choices: dataflow worklist, loan-record layout, C pointer representation
when not exposed by ABI, and optimizer strategy can evolve while preserving
the contract. Accepting additional safe programs can still change portable
build results and diagnostics; record acceptance expansion by version. [E14]

B is most reversible if its lexical rejection is expressly a **checker limit**
rather than permanent semantic rule. That requires a frozen minimum acceptance
set that B actually implements. If RM0 mandates post-last-use acceptance, B
cannot be substituted without breaking conformance. This distinction is a
human design decision, not a coding convenience. [E10, E14]

## Required representation changes for later implementation

- Parser/AST/HIR: local borrow type/expression and distinct semantic binding
  identity; no syntax is approved here. `merit/compiler.py` parameter/return
  grammar at lines ~28–32 and `Checker`/`VarState` [E02–E04].
- Checker: origin/place graph, access permission, all-path validity and
  last-use or lexical span, joins/loops/error edges, alias conflicts, and
  source-span diagnostics. Existing per-call `loans` list at ~1477 is not a
  stored-reference checker [E03, E12].
- Interpreter and C backend: preserve identity and single evaluation while
  carrying a local borrow; borrowed parameters/results already use C pointers,
  but that is not a canonical resource contract [E04].
- Merit-native metadata: `mir_ownership_flow.mrt` has `MirOwnershipBinding`
  with exclusive Alpha.2 flags; it would need a separately versioned authority
  relation rather than repurposing those fields [E16].
- Canonical MIR/protocol: explicit new loan effects and a versioned schema,
  not a reinterpretation of `MirInstruction.ownership`, borrowed-origin rows,
  or Alpha.2 encodings [E05–E06].
- Testing: checker acceptance/rejection, Python oracle/native traces,
  diagnostics, deterministic canonical artifacts, stage-1/stage-2 equivalence,
  platform gates, and unchanged Alpha.2 fixtures [E06–E08].

## Future relationship compatibility

| Future feature | Provisional compatibility | Reason and remaining proof |
| --- | --- | --- |
| Named lifetimes across functions; borrow-containing records | Additional semantic machinery | Local-origin facts are insufficient for stored/returned composite lifetime relationships [E01, E12]. |
| Disjoint fields; slices/tensor views | Additional analysis | Need place/interval overlap and bounds proof; whole-root rejection is sound but incomplete (cases 19–21, 30). |
| Arenas/regions | Additional semantic machinery | Region destruction can invalidate many references at once; membership and escape need explicit rules [E15]. |
| Shared/weak ownership | Additional semantic machinery | Accounting, cycles, upgrade failure, and destructor timing are absent from local loans [E15]. |
| Foreign ownership/retained callbacks | Potentially breaking if raw pointer assumptions become public | Transfer, retention, release provider, and callback lifetime need explicit ABI and hazardous authority [E06, E15]. |
| Pinning/address stability | Naturally orthogonal in F vocabulary; machinery still required | Stable address is not inferred from ownership or borrow permission [E06]. |
| Concurrency/synchronization | Unknown | Thread transfer, race freedom, and memory ordering are outside local-loan proof [E15]. |

## Falsification and follow-up

The preferred F+A combination fails if a concrete safe program needs a
different observable conflict policy, if current Alpha.2 syntax/ABI cannot be
extended without reinterpretation, or if a bounded solver cannot soundly handle
the required acceptance set. Investigate those with a design-review countercase,
then a separately authorized isolated prototype. The current native-test
  environment failures [E08] were resolved for the focused baseline; broader
  cross-platform evidence still belongs to later implementation.
