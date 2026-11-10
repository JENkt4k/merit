# RM0 borrowing decision brief

**Owner-approved preferred design direction, not a frozen language contract.** No compiler
or test implementation has changed. See the [comparison](BORROW_MODEL_COMPARISON.md),
[30 cases](BORROW_MODEL_CASES.md), [risks](BORROW_MODEL_RISKS.md), and
[evidence ledger](BORROW_MODEL_EVIDENCE.md).

## Decision requested

Review the proposed minimum portable acceptance contract and remaining
semantic/type-identity gates for the first Alpha.3 stored-borrow slice. The
owner has selected a preferred direction; this brief does not approve syntax,
implementation, or a normative freeze.

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

Before implementation planning, inspect the Merit-native
`mir_ownership_flow.mrt` binding flags and downstream uses for loan origin and
identity; specify all-path final-use and join behavior, cleanup/destructor
interaction, Python-oracle/native parity, and versioned canonical MIR/protocol
effects. The current source audit gives seams, not proof of readiness. [E02–E08,
E11–E13, E16]

Reference **type identity** must be settled before implementation: whether a
local borrow is a distinct type or mode, whether mutability is a type property,
whether an origin/lifetime relationship participates in type checking, and how
borrowed parameters/results relate to local references. These affect overloads,
generic substitution, ABI/serialization, diagnostics, and observable acceptance.
The spelling of a borrow expression or annotation can wait for syntax review;
it must not silently imply Rust-style reference semantics. [E12, E18]

### Questions still requiring human approval before normative freeze

1. Approve or revise the precise assumptions and case IDs in the proposed
   minimum portable acceptance/rejection table.
2. Settle local reference type identity and parameter/result compatibility,
   without choosing final syntax yet.
3. Define diagnostic identity for unproven origin, conflicting access, and
   escape; decide the acceptance/version policy for later checker improvements.
4. Review the architectural gates and authorize a later bounded implementation
   plan only after the normative spec and evidence contract are complete.

Approval of these questions would guide a later normative spec. It would not
authorize compiler implementation, merge this investigation, or mark RM0
closed. No feature work begins without a separate bounded plan and approval.
