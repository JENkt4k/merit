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
| Serialization | Use the conditional HIR v3/MIR v3/native v6 transition proposed below for this control-flow feature. Preserve byte-identical RM1 and Alpha.2 artifacts and require old readers to reject new versions. |
| Public interface and stages | Publish complete artifacts only after proof. Compare canonical bytes, diagnostics, outputs, and cleanup from independently built stages with no Python semantic fallback. |

## Evidence gate for a later implementation

1. Review the exact accepted/rejected matrix and source spans. Decide whether
   the common-end restriction is sufficient for this slice.
2. Review the proposed version transition and exact join-end encoding before
   writing production artifacts. Reject missing, duplicate, misplaced, or
   path-incomplete loan ends.
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
- Confirm the common join is the loan end even when an arm has no use, and
  approve the versioned representation below before coding.

## Representation review finding

The present MIR v2 reader explicitly rejects any loan-bearing function unless
it has **one block with a return terminator** (`_validate_local_loan_effects`
in `merit/bootstrap/mir_contract.py`). It then checks one global, linear
instruction interval between create and end, and walks only that block for
owned-local liveness. The native MIR v2 writer anchors `end` to the last use's
instruction ID (`canonical_mir_append_one_reference_loan_effects` in
`mir_resolved_source_function_bundle.mrt`). On a branch, that instruction may
not run, and an arm without a use has no end anchor. Reusing those v2 rules
would admit an unproved path or incorrectly reject a sound join.

HIR v2 already has an `if` node kind and local-loan bindings, but its reader
validates identity, shape, and postorder, **not** per-edge loan liveness. An old
HIR v2 reader could therefore accept a branch-bearing loan as if it had RM1's
straight-line proof. Native v5 publication requires canonical MIR v2 and its
strict reader. These are evidenced boundaries, not optional extension slots.

**Recommendation for review:** conditionally emit HIR v3, MIR v3, and native
bundle/protocol v6 only for the approved loan-bearing `if` shape. Keep HIR
v1/v2, MIR v1/v2, and native v4/v5 bytes and readers unchanged for existing
programs. A new v3/v6 reader must reject unknown fields, mixed versions,
incomplete framing, and loan effects with no proof of a common join. The old
readers must reject the new outer versions before interpreting payloads.

The proposed MIR v3 loan `end` effect anchors to **entry of the join block**,
with a block ID and an explicit entry phase, rather than to the last use in
either arm. Its validator must prove that the join postdominates the create
and both arm exits, that all recorded uses are reachable before that entry,
that no owner invalidation conflicts on either path, and that owner cleanup
remains once per reachable exit. A deterministic ordering rule must distinguish
block-entry effects from instruction effects. The exact serialized field names
and numeric discriminants remain for implementation review; no v3/v6 producer
is authorized by this proposal alone.

No decision here changes RM1, R4-R8, `ByteSlice` backing-owner policy, or the
provisional concurrency directions.
