# Comparative borrowing model investigation

**Status:** Provisional RM0 analysis, not an approved language contract. Read
the definitions here before the case classifications in
`BORROW_MODEL_CASES.md`. Evidence identifiers refer to
`BORROW_MODEL_EVIDENCE.md`.

## Executive summary

A and F are not cleanly competing language models. A specifies *how a checker
finds an access restriction's end*; F specifies *which authorities and validity
facts must be kept separate*. F can use A's inferred spans, or B's lexical
spans. F only becomes observably different if it permits another aliasing or
mutation policy. The comparison therefore holds the Alpha.2 alias rule fixed
and tests three implementation contracts: A (inferred spans, bundled authority),
B (lexical spans, bundled authority), F (separated authority with inferred spans).
Under these definitions A and F have identical case outcomes. [E09–E10]

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

**A — inferred loan spans.** A local borrow can hold a reference to an
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

**B — lexical loan spans.** Same reference, origin, access, and ownership
rules, but restrictions persist to the end of the local borrow binding's
enclosing lexical block (or earlier explicit scope exit). Branches conservatively
merge possible origins; a loop may carry a loan only if every iteration and
exit is proven valid. Destruction of the referent before block exit is rejected
even if the reference has no later use. No runtime tracking. This is a
provisional *acceptance contract*, not merely one possible A checker. [E10]

**F — permission-oriented semantics.** Resource *validity*, permission to
read/write, and authority to transfer/destroy are distinct facts. For this
comparison, a local reference holds read or exclusive-write permission to an
origin place; its backing resource remains valid across all possible uses;
the owner retains destruction authority subject to live-loan restrictions.
Access permissions are inferred over the same use-based spans as A. F does
**not** permit aliased mutation, interior mutability, detached weak handles,
or runtime-checked loans in this provisional interpretation. Joins and loops
use conservative union/fixed-point reasoning. No runtime tracking. Hence F is
a semantic decomposition of A's chosen observable policy, not a third set of
accepted programs. A different permission policy would be a new RM0 choice,
not an unannounced consequence of F. [E09, E15]

The terms `Owned<T>`/`Borrowed<T>` in the proposal remain conceptual. Examples
use `let r: borrow T = ...` **only as hypothetical notation**; the actual
surface syntax, explicit borrow expression, and annotation policy are open.

## Semantic versus implementation commitments

| Dimension | Required semantic/acceptance rule in this comparison | Implementation freedom |
| --- | --- | --- |
| Safety | Accepted references are valid at every use; conflicts and premature destruction rejected. | CFG representation, proof algorithm, C storage choice. |
| Portable acceptance | Baseline cases 01–03, 10–12, 18, 24 must be accepted when their stated origins are provable; invalid cases 05–06, 08, 21–23, 27–29 rejected. | Extra safe programs beyond a frozen minimum need a versioned acceptance policy. |
| Inference | A/F accept proven post-last-use owner access (04, 07, 09) subject to path facts; B rejects within the scope. | Precise points-to analysis is not promised. |
| Proof capability | Unknown alias/escape/loop facts cause conservative rejection. | More precision may be added, but changes to corpus acceptance and diagnostics must be recorded. |
| Observability | Move/drop/replace ordering, output, diagnostics, and permitted program set matter. | Runtime representation and loan-solving implementation do not, absent ABI exposure. |

## Comparison and architecture

The 30-case matrix is in `BORROW_MODEL_CASES.md`. For known safe straight-line
local borrows, all models can be useful. A/F additionally admit owner access
after proven last use; B trades that acceptance for simpler lexical bookkeeping.
All reject invalid use, overlapping exclusive access, or unproven escape.
Source components requiring extension include parser/AST/HIR type modes,
`Checker` state and control-flow joins, `OwnershipEffects`, interpreter frames,
native Merit semantic records, canonical MIR effects, C lowering, diagnostics,
serialization/versioning, and parity tests. The existing same-call `loans`
list cannot simply be stretched into a stored-loan proof. [E02–E07, E11–E13]

Theoretical A/F proof work includes origin/alias tracking, backwards use
analysis, forward validity and conflict analysis, joins, and loop fixed points.
B can use lexical intervals but still needs origin, alias, escape, and loop
soundness. Existing compiler complexity is additional: the current reference
checker and MIR pass are not a ready general loan framework. Neither source
inspection nor design reasoning gives a defensible time or performance number.

## Recommendation and falsification

Recommend **F as the semantic vocabulary and A as a candidate proof strategy**,
with the current read/exclusive-write policy preserved. The first independently
verifiable slice should be a local immutable borrow of an addressable owner,
followed by mutable local borrows only after origin, alias, move/drop, and
cleanup evidence is complete. B is a plausible conservative implementation
fallback, but treating B's rejection of post-last-use access as a permanent
language rule would unnecessarily constrain future acceptance. [E09–E14]

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
the exact minimum portable acceptance set; and diagnostics for unproven origin
or loop facts remain unresolved. [E12–E14]
