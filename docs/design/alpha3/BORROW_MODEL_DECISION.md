# RM0 borrowing decision brief

**Owner-approved first-slice semantic direction, not a frozen language contract.** No compiler
or test implementation has changed. See the [comparison](BORROW_MODEL_COMPARISON.md),
[30 cases](BORROW_MODEL_CASES.md), [risks](BORROW_MODEL_RISKS.md), and
[evidence ledger](BORROW_MODEL_EVIDENCE.md). The
[first-slice contract for review](LOCAL_BORROW_CONTRACT.md) records the owner's
later R1–R3/R9 approvals and proposed versioned encoding.

## Decision requested

Review the minimum portable acceptance contract and proposed versioned
representation for the first Alpha.3 stored-borrow slice. The owner has
approved its semantic direction and preferred provisional source spelling;
the design-only PR must be reviewed and merged before implementation. This
brief does not approve production code or a normative freeze by itself.

**Preferred foundation:** F's explicit separation of resource validity,
read/write permission, and transfer/destruction authority, while preserving
Alpha.2's read-sharing/exclusive-write conflict rule. **Recommended proof
strategy:** A's inferred use-based spans where proven sound. B is a conservative
lexical strategy under F, not another semantic foundation. The 30 cases show
no A/F+A acceptance difference under the same alias policy. F adds no interior
mutability, runtime borrow checking, reference counting, or relaxed aliasing.
[E09–E10, E18]

**Proposed first slice:** function-local immutable stored borrows of an
addressable owner or borrowed parameter with provable provenance, readable and
passable to compatible non-retaining calls. Active loans prohibit conflicting
owner mutation, movement, replacement, and destruction. Ownership and cleanup
remain with the owner. Mutable stored borrows, aggregate storage, escape,
general lifetime parameters, Shared/Weak, tensor views, and disjoint subobject
borrowing are deferred. [E01–E04, E12, E18]

## Proposed minimum portable acceptance

Under known single-place provenance, no hidden aliases or later reference uses,
no retaining or unknown-effect calls, and straight-line control flow, a first
conforming checker must accept **01, 02, 04, 07, 09, 18, 24**: one or multiple
immutable local borrows, read and compatible non-retaining call, lexical scope
end, and otherwise valid owner mutation/move/drop after proven final use.
It must reject **05, 06, 08, 22, 23, 28** when they represent conflicting
mutation/move/drop/replacement, invalid use, or unsupported escape. Overlapping
mutable/shared access (**21, 27**) must be rejected if later supported.
Hazard case **29** depends on proven effects: permit non-conflicting effects,
reject conflicts/invalidation, and conservatively reject unknown effects.
Cases **10–17, 19–20, 25–26, 29 with unknown effects, 30** may be conservatively rejected outside
the minimum while their semantics or proofs remain open. Mutable stored-borrow
case **03** is deferred. The comparison document gives the complete table and
assumptions. No conceptual case has run as a compiler test. [E12, E14, E18]

## Alternatives and counterarguments

- **A alone:** viable implementation description, but its phrase "loan span"
  can obscure the separate question of who owns and destroys the referent.
  F provides clearer semantic vocabulary without requiring extra runtime state
  under this policy. [E09]
- **B as permanent language policy:** simpler initial checking and a sound
  conservative option, but cases 04, 07, 09, 13 show safe post-last-use owner
  operations it would reject. B is attractive as an implementation fallback
  for cases it can prove, but B alone fails the proposed required acceptance
  of 04, 07, and 09. [E10, E14, E18]
- **F with novel alias policy:** could eventually support interior mutation,
  runtime-checked aliases, or shared resources, but those are new semantic
  choices with costs and proof obligations, not implied by F. [E15]

The strongest challenge to the recommendation is implementation cost: the
inspected reference checker handles same-call loans and the Python MIR ownership
pass rejects cycles; neither supplies a ready loop-aware local-loan solver.
We have no measured comparative cost. A lexical sub-checker can still handle
simple cases while an inferred or equivalent proof handles the required
post-last-use cases. [E03, E05, E13]

## Reversibility and required evidence

Keep syntax, ABI, protocol, and the exact normative wording of the acceptance
set open for review.
Internal inference algorithms can change; public accepted programs, diagnostics,
cleanup, and serialization compatibility become commitments. A conservative
checker is safe but cannot claim conformance to an acceptance rule it rejects.
Before freezing, make the table's assumptions and error behavior precise and
decide how future acceptance expansions are versioned. [E06, E10, E14, E18]

The focused existing borrow baseline passed **36/36** in 10.15s after the
normal MSYS2 PATH and D: temp setup. Two unconfigured attempts failed in native
compilation; those were environment setup failures, not semantic regressions.
This baseline does not exercise any hypothetical stored-borrow syntax. [E08]

## Human Decisions and Remaining Gates

The owner approved as **preferred design direction**: (1) F separates resource
validity, access, and ownership/destruction without changing Alpha.2 alias
rules; (2) immutable function-local stored borrows are the first proposed
slice; (3) A-style inferred spans and proven post-last-use acceptance are
preferred, while B's lexical rejection is not permanent semantics; (4) final
surface syntax is deferred to separate review. None is a frozen specification
or authorization to implement. [E18]

The [implementation readiness audit](LOCAL_BORROW_IMPLEMENTATION_PLAN.md)
inspected the Merit-native `mir_ownership_flow.mrt` flags and the parser,
checker, HIR/MIR, interpreter, C, replacement, and serialization seams. The
first-slice contract now proposes explicit versioned loan effects and a
minimum straight-line final-use proof. This design audit is not a running
loan solver or compiler parity evidence. [E02–E08, E11–E13, E16, E20]

The owner has since chosen a **distinct non-owning immutable local binding
mode**, with known origin, readable and passable to compatible proven
non-retaining `borrow T` parameters, but not returnable, storable in an
aggregate, or passable as owned `T`. The preferred provisional source form is
`let r: borrow T = borrow x;`. General reference type identity, generics,
mutable stored borrows, and wider syntax remain open. A naive grammar rule
conflicts with an existing accepted type named `borrow`; an in-memory
contextual-token probe parsed both forms. The production parser must preserve
that compatibility. See the [contract](LOCAL_BORROW_CONTRACT.md). [E12, E18]

### Review gates still open before implementation

1. Review and merge the design-only contract with the approved acceptance and
   rejection matrix. It must preserve the accepted `borrow` identifier forms.
2. Review the proposed conditional v1/v2 HIR/MIR and v4/v5 native artifact
   compatibility contract and stable diagnostic categories/spans.
3. Close RM0's design-only ledger under its existing evidence requirements,
   then start a separate bounded implementation PR.

The owner's semantic approval does not itself merge this design PR, mark RM0
closed, or authorize changes to production compiler code in this PR.
