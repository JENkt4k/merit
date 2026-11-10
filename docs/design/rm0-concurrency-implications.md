# RM0 ownership implications from concurrency workloads

**Status:** Design stress test only. All snippets are **proposed pseudo-Merit**;
none is compiled or approved syntax. RM0's preferred F foundation separates
resource validity, access permission, and transfer/destruction authority;
A-style inferred spans are the preferred local proof strategy. The proposed
first slice is immutable function-local stored borrows only. See
`docs/design/alpha3/BORROW_MODEL_DECISION.md`. Cross-thread, captured,
aggregate, or suspended borrows are **not** authorized by local last-use proof.

| Scenario and pseudo-Merit | Expected decision; static guarantee | Runtime duty; RM0 status |
| --- | --- | --- |
| 1. `let r = borrow x; read(r); drop(x);` | Accept only if `read` is the proven final use and ownership rules permit drop; reject `read(r)` afterward. | None for local loan. Proposed RM0 minimum, not implemented. |
| 2. `let r = borrow_mut x; write(r);` | Defer mutable stored borrow; when added, reject any overlapping read/write and track exclusive permission. | None necessarily. Beyond first slice. |
| 3. `let r = borrow x; read(r); mutate(x);` | Required acceptance under known origin/no hidden use; reject mutation before final use. | None. Preferred A-style local proof. |
| 4. `spawn(move buffer)` | Future accept only if the whole value and allocator/release provider are transferable, sender loses ownership, and failed spawn returns or drops once. | Join and cancellation disposition. RM0 R8 open; defer. |
| 5. `spawn(shared immutable_tree)` | Future accept only if transitively safe to share and retention is valid; `immutable` alone does not establish reclamation. | Publication and last-reader release. Shared/Weak deferred. |
| 6. `spawn(move partition)` twice | Future accept only with provably disjoint mutable partitions or two moved owners; reject overlapping mutable regions. | Worker pool/barrier. Disjoint views deferred. |
| 7. `await read(socket, borrow buffer)` | Reject until suspension lifetime, cancellation, and pinned/in-flight buffer rules are specified. | Executor/readiness; partial I/O cleanup. Async deferred. |
| 8. `task(move || read(borrow x))` | Reject escaping captured borrow; scoped capture may later be accepted only if all children join before x drops. | Task scope join/cancel. Closures/scoped threads deferred. |
| 9. `struct Holder { ref: borrow T }` | Reject under first slice; validity needs lifetime relationship across aggregate storage. | None necessarily. Aggregate borrows deferred. |
| 10. `c_register(callback(borrow x))` | Reject unbounded retention; a future scoped registration needs foreign thread affinity, unregister/in-flight drain, and no use after free. | C adapter and callback protocol. RM0 R7 open. |
| 11. `channel.send(move buffer); reuse(buffer)` | Reject sender reuse after successful transfer; on failed enqueue, specify return-or-destroy exactly once. | Bounded queue/atomic publication. Concurrency deferred. |
| 12. `scope { task(move file); cancel_all(); }` | Future accept only with defined cancel-and-join and single destruction on every edge; cancel request alone does not free or join. | Runtime cooperative cancellation. RM0 R3/R8 open. |

## Architectural implications, not new RM0 decisions

The proposed local borrow's origin/identity and final-use proof must remain
separate from **thread transferability**, **safe concurrent sharing**,
**synchronization**, **thread affinity**, and **address stability**. These are
new authority dimensions; F provides vocabulary, not automatic proof. In the
current `mir_ownership_flow.mrt`, `MirOwnershipBinding` records Alpha.2
`owned`, `mutable`, and `needs_drop` flags. Those flags cannot encode a
cross-thread loan, publication order, or in-flight FFI callback without a
new versioned representation. The existing C ABI contract does not establish
thread-safe transfer or callback retention. Do not reinterpret current
serialized discriminants or infer `Send` from `Owned`.

The smallest potential future concurrency foundation is **owned transfer plus
a separately specified transfer/share safety relation, scoped child lifetime,
and publication/synchronization semantics**. A typed bounded channel and
scoped task API could then be library interfaces. This is a recommendation to
validate, not a feature milestone. Sendability, shareability, allocator
provenance, cancellation, memory ordering, and FFI callback affinity need
explicit decisions first. No actor, async, or shared-ownership syntax follows
from RM0.

## Accounting and transactional correctness

| Property | Appropriate authority | Catalog stress cases |
| --- | --- | --- |
| Memory safety and data-race freedom | Language/static boundary plus safe library wrappers; not yet implemented for concurrency. | `actor-buffer`, `locks-atomics`, `ffi-callback` |
| Exact numeric representation, overflow and rounding | Existing Merit exact numeric rules; application chooses currency scale and policy. | `ledger`, `payroll`, `trading` |
| Atomicity and isolation | Database/storage transaction or explicit single-owner protocol; actor-per-account is insufficient for two-account transfer. | `bank-actor`, `bank-transfer`, `accounting-close` |
| Consistency | Application invariants and transactional validation; compiler can enforce types but not balanced accounting by default. | `ledger`, `reporting` |
| Durability | Storage engine/WAL/fsync and documented fault model. | `ledger`, `distributed-transaction` |
| Exactly-once effects | Generally require durable idempotency keys, outbox/deduplication and reconciliation; delivery may repeat. | `payment-outbox`, `invoice-saga` |
| Deterministic replay | Versioned event order, inputs, policies, and numeric rules; scheduling may differ. | `trading`, `audit-replay`, `fraud-stream` |

The [SQLite atomic-commit design](https://www.sqlite.org/atomiccommit.html)
illustrates why crash atomicity is a storage mechanism, not a borrow-checker
guarantee. No built-in database transaction or accounting syntax is justified
by the catalog alone. A safe FFI database adapter and typed Result/decimal
library may be sufficient; test that hypothesis before adding language forms.
