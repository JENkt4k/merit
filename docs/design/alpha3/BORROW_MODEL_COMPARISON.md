# Comparative borrowing model investigation

**Status:** Preferred human design direction, not a frozen language contract. Read
the definitions here before the case classifications in
`BORROW_MODEL_CASES.md`. Evidence identifiers refer to
`BORROW_MODEL_EVIDENCE.md`.

## Executive summary

The owner approved **F as the preferred semantic foundation**: resource
validity, read/write authority, and transfer/destruction authority are separate
facts. **A** is the preferred inferred-span proof strategy; **B** is a
conservative lexical-span strategy. These are not three competing semantics.
Both strategies must enforce Alpha.2's shared-read/exclusive-write policy. F
does not imply interior mutability, runtime borrow checking, reference counting,
or relaxed aliasing. The earlier identical A/F case outcomes arose because F
was evaluated using A's span strategy. [E09–E10, E18]

## Current architecture and scope

The reference grammar has `borrow`/`borrow_mut` parameter and return modes;
`OwnershipEffects` tracks consumption and drops; `Checker` checks borrowed
return origins and same-call loans. The interpreter preserves object identity
and the C emitter lowers borrowed parameters/results as pointers. Canonical
MIR has ownership modes and borrowed origins, but the inspected Python MIR
ownership pass rejects control-flow cycles. None of those facts proves support
for function-local stored loans or path-sensitive lifetime inference. [E01–E07]
The production Merit-native compiler is self-hosted; later implementation must
preserve stage equivalence and Python-oracle independence. [E06]

## Provisional definitions, fixed before case evaluation

Common domain: a **resource** is a value with an identity and destruction
obligation; an **owner** holds the obligation; a **place** is an addressable
whole value or subplace; a **borrow** refers to a place without receiving its
destruction obligation. A loan has an origin, place, access permission, and
validity bound. Existing Alpha.2 `borrow` is read access and `borrow_mut` is
exclusive write access. No model permits a reference to outlive its resource,
move/drop/replace of an occupied place during a conflicting loan, or implicit
transfer of ownership. All three are statically checked, with no new runtime
tracking. Current Alpha.2 programs remain unchanged. [E01, E09]

**A — inferred-span proof strategy under F.** A local borrow can hold a reference to an
addressable owner or a validated borrowed parameter/result. Its source is
evaluated once. Loan restrictions begin when the reference is created and end
after its last possible use on each control-flow path, including uses through
aliases, returns, and calls. Validity of a stored reference is at least as long
as every possible use, but the owner must remain alive whenever it can be used.
Reads can coexist; an exclusive mutable loan conflicts with other accesses to
the same conservatively identified place. At joins, facts are unioned; loops
need a sound fixed point. When origin or last use cannot be proven, reject.
Ownership/destruction stays with the original owner. This definition does not
promise a particular dataflow algorithm or C pointer layout. [E09, E12]

**B — lexical-span conservative strategy under F.** Same reference, origin, access, and ownership
rules, but restrictions persist to the end of the local borrow binding's
enclosing lexical block (or earlier explicit scope exit). Branches conservatively
merge possible origins; a loop may carry a loan only if every iteration and
exit is proven valid. Destruction of the referent before block exit is rejected
even if the reference has no later use. No runtime tracking. This is a
conservative proof limit, not a permanent language rule. B alone cannot meet
the post-last-use acceptance subset proposed below. [E10, E18]

**F — permission-oriented semantics.** Resource *validity*, permission to
read/write, and authority to transfer/destroy are distinct facts. For this
comparison, a local reference holds read or exclusive-write permission to an
origin place; its backing resource remains valid across all possible uses;
the owner retains destruction authority subject to live-loan restrictions.
F does **not** permit aliased mutation, interior mutability, detached weak
handles, or runtime-checked loans in this provisional interpretation. F does
not prescribe a span algorithm. A conforming first implementation must prove
the minimum acceptance cases below, whether using A's analysis or another
sound algorithm. Joins and loops beyond that subset may be conservatively
rejected. No runtime tracking. A different permission policy would be a new
RM0 choice, not an unannounced consequence of F. [E09, E15, E18]

The terms `Owned<T>`/`Borrowed<T>` in the proposal remain conceptual. Examples
use `let r: borrow T = ...` **only as hypothetical notation**; the actual
surface syntax, explicit borrow expression, and annotation policy are open.

## Semantic versus implementation commitments

| Dimension | Required semantic/acceptance rule in this comparison | Implementation freedom |
| --- | --- | --- |
| Safety | Accepted references are valid at every use; conflicts and premature destruction rejected. | CFG representation, proof algorithm, C storage choice. |
| Portable acceptance | The table below proposes the first-slice minimum. Cases 10–12 remain unresolved/deferred; case 29 depends on operation effects. | Additional safe programs may require a versioned acceptance policy. |
| Inference | A-style or equivalent proof must accept 04, 07, 09 when their stated straight-line facts are proven; B alone rejects them within scope. | The worklist/dataflow algorithm is replaceable. |
| Proof capability | Unknown alias/escape/loop facts cause conservative rejection. | More precision may be added, but changes to corpus acceptance and diagnostics must be recorded. |
| Observability | Move/drop/replace ordering, output, diagnostics, and permitted program set matter. | Runtime representation and loan-solving implementation do not, absent ABI exposure. |

## Proposed minimum portable acceptance contract

This is approved **design direction**, not frozen normative text. For mandatory
acceptance, the borrowed place is a single addressable local owner or borrowed
parameter with known provenance. There are no hidden aliases, retaining calls,
later uses through aliases, unknown effects, or control-flow joins. The owner is
mutable only where required. Final use includes every compatible call and read
on that straight-line path. A hazardous capability alone never proves alias
safety. [E18]

| Class | Cases | Proposed first-slice rule and justification |
| --- | --- | --- |
| Required acceptance | 01, 02 | One or multiple immutable local borrows of a provably live owner; compatible reads coexist. |
| Required acceptance | 04, 07, 09 | Owner mutation, move, or destruction after the provable final borrow use, when no other restriction remains and Alpha.2 ownership/cleanup rules allow the operation. No later reference use. |
| Required acceptance | 18, 24 | Explicit inner-scope end before owner operation; reading through a local borrow and passing it to a proven non-retaining compatible borrowed parameter. |
| Required rejection | 05, 06, 08, 22, 23, 28 | Conflicting mutation, move, destruction, replacement, use after invalidation, or escape from the local-only boundary. |
| Conditional effect rule | 29 | A proven non-conflicting operation is not rejected merely because it is hazardous; reject a proven conflict/invalidation, and permit conservative rejection if effects are unknown. |
| Required rejection when applicable | 21, 27 | Overlapping mutable/shared access is unsafe if mutable stored borrows are later added. |
| Permitted conservative rejection | 10–17, 19–20, 25–26, 29 with unknown effects, 30 | Reassignment, shadowing, joins, branches, error edges, loops, subplaces, relay, nested cleanup, unknown effects, and views are outside the minimum, even when a particular instance is safe. |
| Deferred specification | 03, 10, 12, 15, 19–20, 25, 29–30 | Mutable stored borrows, assignment/phi origin, `try` cleanup, projection/disjointness, relay, effects, and views need separate rules. Portable acceptance of 11, 13–14, 16–17, and 26 also remains deferred. |

Mandatory rejection describes unsafe behavior where the construct is otherwise
supported; an unsupported future construct may fail earlier as unsupported.
Outside the required subset, a first checker may reject when it cannot prove
validity or non-conflict. Later acceptance expansion can change portable build
results and must be recorded, not assumed compatibility-neutral. [E14, E18]

## Comparison and architecture

The 30-case matrix is in `BORROW_MODEL_CASES.md`. For known safe straight-line
local borrows, both strategies can be useful. A-style inference additionally
admits owner access after proven last use; B trades that acceptance for simpler
lexical bookkeeping and cannot alone meet the proposed minimum.
All reject invalid use, overlapping exclusive access, or unproven escape.
Source components requiring extension include parser/AST/HIR type modes,
`Checker` state and control-flow joins, `OwnershipEffects`, interpreter frames,
native Merit semantic records, canonical MIR effects, C lowering, diagnostics,
serialization/versioning, and parity tests. The existing same-call `loans`
list cannot simply be stretched into a stored-loan proof. [E02–E07, E11–E13]

Theoretical A-style proof work includes origin/alias tracking, backwards use
analysis, forward validity and conflict analysis, joins, and loop fixed points.
B can use lexical intervals but still needs origin, alias, escape, and loop
soundness. Existing compiler complexity is additional: the current reference
checker and MIR pass are not a ready general loan framework. Neither source
inspection nor design reasoning gives a defensible time or performance number.

## Recommendation and falsification

The owner selected **F as preferred semantic vocabulary and A as preferred proof strategy**,
with the current read/exclusive-write policy preserved. The first independently
verifiable slice should be a local immutable borrow of an addressable owner,
followed by mutable local borrows only after origin, alias, move/drop, and
cleanup evidence is complete. B is usable for cases it can prove, but B alone
cannot satisfy the proposed post-last-use acceptance subset. [E09–E14, E18]

This recommendation is falsified or must be narrowed if a concrete case shows
F's separated authority changes observable behavior under the stated policy;
the current representation cannot encode a safe local loan without breaking
Alpha.2; a focused implementation prototype cannot prove joins/loops safely;
or differential stage/oracle evidence reveals changed cleanup/diagnostics.
Those are **later** experiments, not authorization to implement now.

## Open questions

Syntax and type identity; whether reassignment ends a prior loan; whether
subplace disjointness is guaranteed; how a local borrow of a temporary is
handled; whether acceptance of further provably safe programs is versioned;
the exact normative wording of the proposed minimum subset; and diagnostics
for unproven origin or loop facts remain unresolved. [E12–E14, E18]
