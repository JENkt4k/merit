# RM0 immutable local borrow: implementation readiness audit

**Status:** Bounded implementation plan, not an RM0 freeze or authorization to
change the compiler in this PR. The owner has approved F's separation of validity,
access permission, and transfer/destruction authority, A-style final-use
proof, and Alpha.2 shared-read/exclusive-write rules. The active
[`ALPHA3_RESOURCE_MODEL.md`](../../../ALPHA3_RESOURCE_MODEL.md) still requires
reviewed and merged R1–R3 and R9 design decisions before feature
implementation. The [first-slice contract](LOCAL_BORROW_CONTRACT.md) records
the owner's identity, compatibility, diagnostic, and provisional spelling
direction plus an encoding proposal for that review. No concurrency decision
reopens the local rule.

## Smallest user-visible capability

An immutable function-local borrow binds a non-owning reference to one
addressable local owner or borrowed parameter of known origin. The binding can
read the referent or pass it to a compatible **non-retaining** shared-borrow
parameter. It cannot be assigned into an aggregate, returned, moved as an
owned value, or used after the owner becomes invalid. Its live loan prevents
conflicting owner mutation, move, replacement, and drop. When all possible
uses are complete, those owner operations become legal in the same lexical
scope. Owner cleanup and destructor authority never transfer to the borrow.

This is the first coherent feature boundary. An internal origin/liveness pass
can be tested earlier, but by itself is not a language feature or evidence of
replacement-compiler support. Joins, loops, reassignment, mutable stored
borrows, field/disjoint loans, stored references in aggregates, borrowed
returns through local bindings, generic reference arguments, escaping captures,
and cross-thread use remain outside this first boundary unless an existing
Alpha.2 form already supports them independently.

## Acceptance and rejection matrix

The following `borrow_local(x)` and `local_ref<T>` are **abstract test notation**,
not proposed Merit syntax. Each row assumes one known origin, no hidden alias,
straight-line control flow except an explicit lexical block, and known
non-retaining call effects. Match the case IDs in
[`BORROW_MODEL_CASES.md`](BORROW_MODEL_CASES.md).

| Case | Minimal action after `r = borrow_local(x)` | Required result and evidence |
| --- | --- | --- |
| 01 | `read(r)` | Accept; referent remains valid; owner drops once at normal exit. Repeat with `x` a borrowed parameter of known origin. |
| 02 | `s = borrow_local(x); read(r); read(s)` | Accept two shared reads, one owner cleanup. |
| 04 | `read(r); mutate(x)` | Accept after proven final use, including while `r` remains lexically in scope. |
| 07 | `read(r); consume(x)` | Accept transfer after final use; destination becomes sole owner. |
| 09 | `read(r); drop(x)` | Accept one destruction after final use. |
| 18 | `scope { r = borrow_local(x); read(r) }; mutate(x)` | Accept; scope end is a valid loan boundary. |
| 24 | `inspect(r); read(r)` where `inspect` is a known non-retaining shared-borrow call | Accept and preserve the referent; reject an unknown or retaining callee until effects are proven. |
| 05 | `mutate(x); read(r)` | Reject conflicting write during a live loan. |
| 06 | `consume(x); read(r)` | Reject move while the loan may be used. |
| 08 | `drop(x); read(r)` | Reject destruction while the loan may be used; no destructor runs twice. |
| 22 | `return r` from a function-owned `x` | Reject escape; no dangling result. |
| 23 | `holder.field = r` or vector/enum storage | Reject aggregate escape under the local-only contract. |
| 28 | `replace(x, fresh); read(r)` | Reject replacement of a still-borrowed owner; the old value is not destroyed before the final read. |

Also reject use of `r` after owner destruction, a borrow of a temporary without
stable address, unknown origin, borrowed reference consumed as an owned
argument, and simultaneous mutable access through an Alpha.2 `borrow_mut`
call while a shared local loan remains live. After final use, permit otherwise
valid owner operations. Cases 03, 10–17, 19–21, 25–27, 29–30 have the limits
and conditional treatment in the decision brief; none can silently become a
required first-slice acceptance case.

## Compiler boundary audit and minimal change

| Boundary now | Required first-slice change | Compatibility gate |
| --- | --- | --- |
| Parser and AST: `merit/compiler.py` has `borrow`/`borrow_mut` only on parameters and results; `let`/`var` require a value `type_ref`, and borrowed results are rejected in owned bindings (`M5304`). | Introduce one explicit local-borrow declaration and source expression after a narrowly approved spelling. Assign its existing-style semantic binding ID and source span. Do not reinterpret old `let` or parameter syntax. | Old parse trees, accepted/rejected syntax, and diagnostics stay unchanged. |
| Reference checker: `VarState` tracks owner move/drop and parameter mode; per-call loan checks are temporary, not stored-loan liveness. | Track local reference binding, origin binding/place, immutable permission, and all possible straight-line uses. Check owner effects against live loans; end restrictions after proven final use. Fail closed on unsupported control flow, unknown provenance/effects, or escape. | Cases 01/02/04/07/09/18/24 accept; 05/06/08/22/23/28 reject. Preserve M510x/M530x behavior on old forms; assign new diagnostic identity only after review. |
| HIR and semantic lowering: `bootstrap-hir-v1` expression records carry type/binding information, but no persistent local-loan identity. | Add distinct validated local-reference provenance and read/call-use facts; do not encode authority as a numeric `T` type or reuse a borrowed-return origin field. | Same source selects the same binding IDs and ordered evaluations in Python and native stages. |
| Canonical MIR: `bootstrap-mir-v1` has `borrow` instructions and local ownership modes, while `MirFunction.borrowed_origin` describes returned parameter references. Python ownership planning is acyclic; Merit-native `MirOwnershipBinding` only carries Alpha.2 owned/mutable/drop flags. | Version a separate local-loan effect/metadata record with origin, permission, create/use/end points and source identity. Prove final use before cleanup. Do not repurpose existing mode discriminants or flags; retain old v1/v4 decoding for old artifacts. | Validate ordering and complete framing; compare canonical MIR bytes across reference/native and stage 1/2; reject malformed or unversioned new records. |
| Interpreter: borrowed parameters/results preserve object identity; local values are ordinary bindings. | Represent a local reference as a non-owning alias to the same owner object with tracked validity, never as an implicit copy or independent drop obligation. | Read trace and destructor count match native execution; no use after invalidation. |
| C backend: borrowed parameters/results are pointers; local cleanup is owner-based. | Lower local immutable reference to a pointer-like internal value only after static proof. Materialize its source once; preserve left-to-right evaluation and owner address validity during use. Do not expose a new public C parameter/field ABI in this slice. | Existing C/header/layout bytes stay stable for old programs; new program C is deterministic; `const` access cannot mutate the referent. |
| Production replacement and serialization: self-hosted compiler emits complete native v4 MIR/C/header artifacts through the public project interface; Python is an independent oracle. | Implement the same syntax, identity, checker proof and new versioned effects in Merit-native source. Advance protocol/schema only as required by the approved representation, preserving old artifact decoding and fail-closed behavior. | No Python fallback; reference/native diagnostics and accepted/rejected corpus converge; isolated stage 1/2 and public project builds agree on MIR/C/header and execution. |

Physical C pointers are an implementation technique, not the semantic type or
address-stability rule. The owner must outlive every use; after final use a
pointer may remain physically present but must never be read. A borrow has no
destructor. Existing owner drop, `replace`, implicit cleanup, early return,
error propagation, and custom destructor order remain exactly as Alpha.2.
No new allocation or capability is implied by local borrowing.

## Independent implementation and validation sequence

1. **Close the RM0 design gates.** Review the approved reference identity,
   compatibility, diagnostic, and provisional syntax contract and the proposed
   encoding. Merge the design-only R1–R3/R9 decisions and precise Alpha.2
   compatibility language in the RM0 ledger.
2. **Isolate the checker proof.** Add table-driven origin/liveness tests using
   the approved AST form. Start with one local owner, then two shared borrows,
   borrowed-parameter origin, non-retaining call, and post-final-use
   mutation/move/drop. Pair every accepted case with a live-loan or escape
   rejection. Compare exact diagnostic code/span/note for new forms.
3. **Add runtime and representation parity.** Check interpreter/native output,
   single evaluation, early/normal cleanup, custom destructor count, and
   deterministic HIR/MIR/C/header. Implement the same proof in the native
   compiler; reject unsupported joins, loops, unknown calls, and malformed
   serialized loan records rather than silently accepting them.
4. **Cross-stage and platform evidence.** Compile fresh isolated stage 1/2
   compilers through the public project interface, compare new canonical
   artifacts and old Alpha.2 fixture digests, then run focused replacement
   accepted/rejected cases. Only at the coherent boundary run affected
   subsystem gates; run full clean Windows and Ubuntu gates before claiming a
   feature PR ready for merge.

Baseline already run on synchronized `main` (PR #139 merge `8030d10`):

```text
python -m pytest -q tests/test_epoch_iii_borrowed_returns.py tests/test_ephemeral_borrow_boundary.py
36 passed in 9.06s (Windows, MSYS2 UCRT64 GCC, D: temp)
```

Future independent commands, once the tests exist:

```text
python -m pytest -q tests/test_alpha3_local_borrow.py
python -m pytest -q tests/project/test_alpha3_local_borrow_replacement.py
python scripts/gate.py fast
python scripts/gate.py subsystem
python scripts/gate.py self-hosting
python scripts/gate.py full --durations 50
```

Use external D: temporary paths for local Windows logs and pytest basetemp.
The final-tree full gate and authoritative hosted checks remain candidate-PR
gates, not per-edit checks. The legacy `Vec<Sample>` replacement gap and all
concurrency, indexed-ring, shared/weak, region, pinning, and foreign-ownership
features stay on separate tracks.

## Remaining review gate before a public feature change

The owner has approved local reference identity, compatibility, minimum
acceptance/rejection, cleanup, diagnostic categories/spans, and the preferred
provisional source form. The in-memory grammar probe found that a naive
keyword alternative breaks the existing accepted `struct borrow` type, while
a contextual alternative preserves it; production parser tests must cover
this. The proposed conditional HIR/MIR v1/v2 and native artifact v4/v5
compatibility contract in [the first-slice contract](LOCAL_BORROW_CONTRACT.md)
still needs design-only review and merge. RM0's active ledger also requires
R1–R3/R9 normative closure and explicit R4–R8 deferral before implementation.
No new concurrency property blocks this local slice. Specific numeric
diagnostic/effect IDs and internal layout are delegated to implementation,
with named canonical definitions and unchanged Alpha.2 encodings.
