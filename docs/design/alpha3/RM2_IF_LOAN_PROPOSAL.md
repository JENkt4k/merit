# RM2 proposal: immutable local loans across one `if` join

**State:** Design proposal for review after RM1 merged in PR #142. This file
does not freeze semantics, authorize compiler changes, or extend RM1. The
existing [RM1 contract](LOCAL_BORROW_CONTRACT.md) remains authoritative.

## Why this slice

RM1 proves a fixed final use in straight-line code and capability blocks. The
reference checker rejects a function with a local loan and any `if`, `while`,
`match`, or `try_let` (`Checker.prove_local_loans` in `merit/compiler.py`). The
native source proof also returns its unsupported status on an `if` statement
(`derive_source_local_loan_uses` in `mir_source_function_records.mrt`). A single
acyclic `if` join is the next useful proof boundary. It can establish branch
read permission and a common post-branch owner action without choosing loop
fixed points, merged origins, mutable references, or new syntax.

The proposed **minimum** keeps one immutable loan of a known owner created
before the `if`. Either arm may read it or pass it to a proven non-retaining
`borrow T` parameter. Both arms fall through to one join. The owner remains
valid and unchanged until that join. The loan ends at the join before an owner
write, move, replacement, or drop. An arm with no reference use still traverses
the same join. No branch creates or reassigns the reference or origin. The
program has no loop, `match`, `try`, escaping reference, return from an arm, or
unknown/retaining effect in this proposed minimum.

This is a conservative common-end proof: it does not promise owner mutation
inside an arm after that arm's last use. Such path-specific early ends are a
separate acceptance decision. The reference itself has no cleanup; the owner
retains exactly-once destruction authority on every path.

## Proposed executable matrix

These are candidate programs for a later implementation PR. They are **not**
claims about current compiler acceptance. Each complete test would include a
`module`, function, and required declarations using existing Merit syntax.

| ID | Shape | Proposed outcome and reason |
| --- | --- | --- |
| I01 | `var x:i32=1; let r: borrow i32=borrow x; if x { print(r); } x=2; print(x);` | Accept: read on true edge, common end, then owner write. Output `1,2` when condition is true. |
| I02 | An owned `Box` origin with `if c { print(r.value); } else { print(r.value); } drop(x);` | Accept: both edges read, common end, one owner destruction and one custom-destructor trace. |
| I03 | `if x { inspect(r); } else { print(0); } x=2;` | Accept only when `inspect(borrow p:T)` is proven non-retaining; one edge has no use. |
| I04 | `if x { x=2; } print(r);` | Reject: one reachable edge writes the origin before a later use. Preserve a conflict diagnostic with creation note. |
| I05 | `if x { drop(x); } print(r);` | Reject: one reachable edge invalidates the origin before a later use. |
| I06 | `if x { return r; } print(r);` | Reject reference escape; early-return joins are outside the minimum even when the return value is changed. |
| I07 | `if x { unknown(r); } print(r);` | Reject unless the call has a proven compatible non-retaining effect. |
| I08 | `if x { print(r); } while x { print(r); }` | Fail closed: loop loan proof is outside this slice. |

The later tests must vary true/false conditions, owner types with observable
destructors, both arm orders, and nested calls with proven effects. The accepted
shapes must compare Python interpreter, Python C, Merit-native project C, and
fresh stage-1/stage-2 output and cleanup. Rejected shapes must fail before
project artifact publication with matching stable diagnostics and spans.

## Compiler and representation audit

| Boundary | Required work before acceptance |
| --- | --- |
| Parser and binding IDs | Reuse existing `if` and contextual local-borrow syntax. Preserve origin/reference binding IDs and branch source spans; no new syntax. |
| Python checker | Replace the blanket `if` rejection only for the bounded shape. Compute reachable uses and conflicting owner effects on both arms; prove owner validity at the join. Unsupported flow still fails closed. |
| Python HIR/MIR and interpreter/C | Emit a branch and common loan end with deterministic instruction identity; execute the condition once; compare true/false traces and owner cleanup. |
| Merit-native proof and backend | Extend source/CFG proof and writer together. The current source-use proof rejects `if`; its linear last-use statement index is insufficient by itself to prove a branch join. Never narrow diagnostic 907 until complete v5 C/header/MIR production and validation succeeds. |
| Serialization | Audit whether HIR v2, MIR v2 loan effects, and native v5 can unambiguously express a loan end at a CFG join and validate all predecessor paths. Existing linear create/use/end validation is not evidence of this. If not, propose a conditional new version with old-reader rejection; preserve byte-identical RM1 and Alpha.2 artifacts. |
| Public interface and stages | Publish complete artifacts only after proof. Compare canonical bytes, diagnostics, outputs, and cleanup from independently built stages with no Python semantic fallback. |

## Evidence gate for a later implementation

1. Review the exact accepted/rejected matrix and source spans. Decide whether
   the common-end restriction is sufficient for this slice.
2. Prove the representation can encode and strictly validate the join, or
   review a version transition before writing production artifacts. Reject
   missing, duplicate, misplaced, or path-incomplete loan ends.
3. Add focused checker, execution, HIR/MIR, native-v5, malformed-artifact, and
   legacy-byte regressions. Test both branch outcomes and destructor paths.
4. Build fresh isolated stage-1/stage-2 compilers through the public project
   interface and compare independent acceptance, rejection, artifacts, and
   traces. Qualify final code with subsystem, self-hosting, and hosted Windows/
   Ubuntu full gates under the repository gate policy.

## Decisions requiring review

- Approve I01-I03 as the minimum, or prefer the smaller branch-local-only loan
  with no loan live across a join. The latter proves less user-visible behavior.
- Decide whether owner operations inside an arm after that arm's final use are
  deliberately deferred. The proposal defers them.
- Confirm the common join is the loan end even when an arm has no use. The
  serializer/validator audit must settle how this is encoded before coding.

No decision here changes RM1, R4-R8, `ByteSlice` backing-owner policy, or the
provisional concurrency directions.
