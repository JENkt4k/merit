# Thirty conceptual borrowing cases

**Read definitions in `BORROW_MODEL_COMPARISON.md` first.** These fragments
are **not executable Merit programs**. `let r: borrow T = borrow x` and
`borrow_mut x` as expressions are hypothetical notation. Existing `fn
f(borrow x:T)` parameter modes, `drop`, `replace`, `if`, `while`, and `try`
are illustrative of current syntax, but their combination with stored locals
is unsupported. `use(r)` reads; `edit(r)` writes; `move(x)` means a consuming
value transfer. `scope { ... }` indicates a lexical block, not literal grammar.
`?` below means specification or proof is missing; it is not permission to
accept. `S` safe under stated assumptions, `U` unsafe, `D` dependent. F is the
preferred semantic foundation; the A and B columns compare proof strategies
under F. `F+A` records the prior F evaluation with A-style spans, not a third
algorithm. Outcomes are provisional; no outcome is an Alpha.3 compiler result. Alpha.2
`U/S` means **unsupported syntax**, not an observed diagnostic. Current
call/return baseline evidence is [E01–E08].

All cases require a checker to prove the referent remains valid at every use,
that write authority has no conflicting alias, and that destruction happens
once after the final permissible use. Each case adds a specific obligation.

| ID | Conceptual fragment and intent | Safety; relationships, paths, proof/cleanup | Alpha.2 | A | B | F+A | Complexity; compatibility; why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | `let r:borrow T=borrow x; use(r);` | S if `x` live; one read loan; prove origin; owner cleans once. | U/S | Accept | Accept | Accept | Local origin; new syntax, no old behavior change. |
| 02 | `r=borrow x; s=borrow x; use(r); use(s);` | S; two read permissions; prove both share live `x`; one owner cleanup. | U/S | Accept | Accept | Accept | Alias accounting; read/read coexist. |
| 03 | `r=borrow_mut x; edit(r);` | S if `x` mutable; one exclusive write loan; no other access; owner cleans once. | U/S | Accept | Accept | Accept | Mutability and exclusivity; preserves call rule. |
| 04 | `r=borrow x; use(r); edit(x);` | S only if edit is after last possible use and `x` mutable; prove no hidden alias or destructor read. | U/S | Accept | Reject | Accept | Backwards liveness; B loan lasts to scope end [E10]. |
| 05 | `r=borrow x; edit(x); use(r);` | U under shared-read policy: write conflicts with still-needed read loan. | U/S | Reject | Reject | Reject | Same-place conflict; must not rely on apparent benign value. |
| 06 | `r=borrow x; move(x); use(r);` | U: resource can be transferred/destroyed before read; prove consume and loan conflict. | U/S | Reject | Reject | Reject | Consumption site/span; Alpha.2 moves unchanged. |
| 07 | `r=borrow x; use(r); move(x);` | S if no later alias use and transfer valid; destruction obligation moves exactly once. | U/S | Accept | Reject | Accept | Last-use proof; B retains restriction. |
| 08 | `r=borrow x; drop(x); use(r);` | U: dangling use; reject before drop, no double cleanup. | U/S | Reject | Reject | Reject | Drop conflict and provenance. |
| 09 | `r=borrow x; use(r); drop(x);` | S if no later use; owner dropped exactly once. | U/S | Accept | Reject | Accept | Inferred end versus lexical end. |
| 10 | `r=borrow x; r=borrow y; use(r);` | D: safe if reassignment releases old loan, both owners live; choose overwrite semantics and show old `x` cleanup. | U/S | ? | ? | ? | Assignment and alias tracking unresolved [E12]. |
| 11 | `r=borrow x; scope { r2=borrow y; use(r2); } use(r);` | S if x/y live; shadow binding IDs distinct; each loan follows its binding. | U/S | Accept | Accept | Accept | Existing semantic binding IDs help; syntax new. |
| 12 | `if c { r=borrow x } else { r=borrow y }; use(r);` | D: safe if both owners live and type/permission agree; union origins at join. | U/S | ? | ? | ? | Phi/join provenance; acceptance precision unresolved. |
| 13 | `if c { use(r) }; edit(x);` where `r` borrows `x` | S if no path uses `r` after edit; prove branch-dependent last use. | U/S | Accept | Reject | Accept | CFG liveness; B rejects in scope. |
| 14 | `r=borrow x; if c { return value }; use(r);` | S if early-return cleanup cannot destroy `x` before any actual use; prove both edges, single cleanup. | U/S | Accept | Accept | Accept | Edge-specific cleanup; current return traces preserved. |
| 15 | `r=borrow x; try operation(); use(r);` | D: safe if error-edge cleanup ends loan before destroying `x`, success keeps `x` live. | U/S | ? | ? | ? | `try` edge and ownership transfer require normative trace. |
| 16 | `while c { r=borrow x; use(r); }` | S if x live across iterations; no carry/escape; prove each iteration ends before next. | U/S | Accept | Accept | Accept | Loop fixed point for A/F; B block-local scope. |
| 17 | `r=borrow x; while c { use(r); maybe_drop(x); }` | U if drop may run before later iteration/use; reject unless drop impossible. | U/S | Reject | Reject | Reject | Loop-carried liveness and path proof. |
| 18 | `scope { r=borrow x; use(r); } edit(x);` | S; scope ends both loan forms before edit; x remains owner. | U/S | Accept | Accept | Accept | Lexical baseline; no difficult inference. |
| 19 | `r=borrow x.field; use(r);` | D: safe if field address stable while used and enclosing owner not moved; conservative whole-root alias is sound. | U/S | ? | ? | ? | Place projection and address stability unresolved. |
| 20 | `a=borrow_mut x.left; b=borrow_mut x.right; edit(a); edit(b);` | D: safe only if fields are proven disjoint and no owner-wide mutation; otherwise reject. | U/S | ? | ? | ? | Disjointness guarantee deferred; whole-root rejection sound. |
| 21 | `a=borrow_mut x.left; b=borrow_mut x.left; edit(a); edit(b);` | U: simultaneous exclusive loans overlap. | U/S | Reject | Reject | Reject | Same-place alias conflict. |
| 22 | `r=borrow local; return r;` from owned local | U: local cleanup would invalidate return; reject. | U/S | Reject | Reject | Reject | Existing return-origin rule [E01/E03] preserved. |
| 23 | `owned_record.ref=r;` | U under local-only contract: outlives scope unless separately specified; reject even if particular use seems safe. | U/S | Reject | Reject | Reject | Aggregate escape requires later type/lifetime model. |
| 24 | `r=borrow x; inspect(r); use(r);` | S if call cannot retain/drop/mutate x and r live afterward; prove callee mode/effects. | U/S | Accept | Accept | Accept | Call transfer; existing call mode is baseline. |
| 25 | `r=borrow p; return expose(r);` where p borrowed parameter | D: safe if return origin remains p and relay validates mode; local syntax new, current ephemeral relay exists. | U/S | ? | ? | ? | Preserve [E01/E03] return-origin rule; specify local relay. |
| 26 | `r=borrow x; scope { owned y=make(); use(r); } return;` | S if x/y live at uses; deterministic reverse cleanup remains; reference has no drop. | U/S | Accept | Accept | Accept | Cleanup trace across nested scope. |
| 27 | `r=borrow_mut x; s=borrow x; use(s); edit(r);` | U unless first exclusive loan ended before `s` starts; both aliases live by final use. | U/S | Reject | Reject | Reject | Mixed alias prohibition. |
| 28 | `r=borrow x; x=make(); use(r);` | U if assignment replaces/destroys old x; reject; one old-value destruction only. | U/S | Reject | Reject | Reject | Replacement effect must conflict with active loan. |
| 29 | `r=borrow x; with capability io { hazard(x); }; use(r);` | D: accept only with proven non-conflicting effects and live x; reject a proven conflict/invalidation; unknown effects permit conservative rejection. | U/S | Conditional | Conditional | Conditional | Capability does not imply alias safety; effect contract needed. |
| 30 | `a=view_mut(tensor,0..4); b=view_mut(tensor,4..8); edit(a); edit(b);` | D: safe only with proven bounds, nonoverlap, stable backing lifetime; otherwise reject. | U/S | ? | ? | ? | Hypothetical tensor syntax; later slice needs interval/shape proof. |

## Matrix interpretation and proof obligations

This table retains the complete A/B/F investigation matrix with F interpreted
through A. `Accept` assumes the common domain's
origin, type, and validity premises are proven. It is not a promise that the
current compiler accepts the notation. `Reject` is a proposed mandatory
outcome under the provisional rule. `?` means the model definition alone does
not settle observable acceptance, or a required semantic fact is absent.

Cases 04/07/09/13 distinguish inference from lexical restriction. None
distinguishes A from F+A under the fixed alias policy; a future F policy that
allows interior mutation or runtime-checked aliases must be compared anew.
Cases 10/12/15/19/20/25/30 identify specification gaps rather than evidence
for any strategy. Case 29 is effect-dependent: a proven non-conflicting hazard
can be allowed, a proven conflict must be rejected, and unknown effects may be
conservatively rejected. Cases 06/08/17/21/22/23/27/28 are safety counterexamples.
Cases 14–17 require per-edge or loop proof; a solver that cannot prove the
facts rejects, regardless of apparent intent. An A-style checker must compute
a sound fixed point over loan origin, liveness, and access restrictions for
supported loops. B still needs a
sound origin and exit analysis; lexical intervals alone do not prove safety.

The proposed **minimum portable acceptance** is cases 01, 02, 04, 07, 09, 18,
and 24 under the straight-line assumptions in the comparison document; case 01
also covers a borrowed parameter when its origin and remaining validity are
proven. Cases
10–12 are expressly *not* required acceptance. Case 03 describes deferred
mutable stored borrows; its theoretical `Accept` does not authorize that first
slice. A/B/F+A outcomes outside the minimum express conditional model behavior,
not a promise that every conforming first checker must accept them.

Only existing Alpha.2 parameter/ephemeral-return forms can be checked against
the current compiler. All local-reference fragments are unsupported in Alpha.2;
therefore no row is labeled "verified accepted" or "verified rejected" for
the full fragment. This avoids turning conceptual examples into fake tests.
