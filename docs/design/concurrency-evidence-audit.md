# Concurrency lifecycle evidence audit

**Status:** Post-PR #138 design evidence on the owner-approved provisional
directions. This does not freeze RM0, authorize concurrency implementation,
or introduce Merit syntax. See the [lifecycle](concurrency-provisional-lifecycle.md),
[RM0 decision brief](alpha3/BORROW_MODEL_DECISION.md), and
[sensor experiment](sensor-pipeline-experiment.md).

## Evidence and consistency findings

| Finding | Existing evidence | Consequence |
| --- | --- | --- |
| F+A local proof remains separate from cross-thread authority. | RM0 cases 04, 07, 09 permit owner mutation/move/drop only after proven final local borrow use; cases 05, 06, 08 reject a still-live borrow. Cases 22 and 23 reject local-borrow escape. | A sender may move an owned value only after local loans end. No local last-use proof establishes transferability, safe destruction elsewhere, publication order, or child completion. |
| Returned failure can preserve an owned value without new syntax in the current *single-threaded* subset. | `test_single_thread_owned_fifo_uses_two_vectors_without_indexed_take` constructs an owned `Packet`, returns it as `Rejected(Packet)` from a value-consuming function, and checks its identity/one destructor trace after matching. | The proposed nonblocking result shape is expressible locally. Cross-thread safety remains unproved. |
| A bounded FIFO is expressible without indexed owned take. | The same focused reference/native test uses two `Vec<Packet>` stacks, a total-length capacity check, `vec_pop`, and `vec_push`; it observes FIFO order and exactly-once drops through wrap-like refill. | Do not require a new indexed-take primitive merely to build a single-threaded bounded FIFO. A contiguous occupied-slot *ring* still lacks demonstrated indexed take; two stacks may have different latency and allocation behavior. |
| `vec_replace` is not an owned take. | `spec/OWNERSHIP.md` specifies that it destroys the displaced value; `vec_get` cannot copy an owned element; `vec_pop` takes only the tail. | An `Option<T>` slot strategy needs a value-returning replacement or another proven representation. Do not treat destroying the old slot as returning it. |
| Close plus drain needs pending-send ordering. | The provisional contract says publication and close are linearizable. | End-of-stream requires closed, queue empty, **and all earlier admitted/pending publications resolved**. Otherwise a receiver could observe EOF before an already accepted message appears. |
| Cancellation request is distinct from an acknowledged outcome. | Existing F ownership authority and the proposed lifecycle put the value in operation custody until `Sent`, `Rejected`, or `Cancelled(value)` is resolved. | If a caller abandons the operation/result, an owned completion handle or explicit disposal path must retain responsibility. A bare callback or timeout cannot silently leak or duplicate the value. |
| Exact-once destruction is an in-process cleanup obligation. | Alpha.2 destructors and allocator provenance are deterministic for current owned values. | Race tests count one terminal owner and one destructor invocation under cooperative execution. Power failure, process abort, and external side-effect replay are outside this claim; a destructor that itself fails needs a separate policy. |
| Failed spawn cannot expose partially moved captures. | The provisional rule returns the original task and captures on failure; current ownership rules forbid implicit copies. | A trusted spawn boundary must either finish capture construction before the failure point or define unwind cleanup and return of every transferred capture. A detached task cannot borrow a parent local under RM0's first slice. |

The two-stack probe is intentionally narrower than the future channel. It has
no concurrent handle, atomic state, cancellation, close, receiver teardown, or
executor affinity. Its capacity check and destructor trace establish only
current single-threaded language/library expressibility. The full sensor
project's `Vec<Sample>` replacement-compiler rejection is tracked separately;
the probe uses the independent reference/native route and does not resolve it.
The complete focused sensor test file passed **5/5 in 21.44 seconds** on
Windows with MSYS2 UCRT64 GCC and D: temporary paths after this addition.
No subsystem or full gate was run for this design-evidence follow-up.

## Proposed race and lifecycle test matrix

All rows below are **future specifications**, not runnable concurrency tests.
Instrument a noncopyable packet with unique ID, destructor count, allocator
provider ID, and allowed release context. Record invocation/response intervals
and one linearization order. The terminal accounting invariant is: each packet
is returned to an owner, delivered to a receiver, recovered at teardown, or
destroyed once; no packet has two terminal owners.

| ID | Forced interleaving or fault | Permitted result and required accounting |
| --- | --- | --- |
| S1 | Capacity available; send commits before receive | `Sent`, then one receiver obtains packet; sender cannot reuse it. |
| S2 | Queue full before send's decision point | `Rejected(Full, original packet)`; queue unchanged; caller drops or retries once. |
| S3 | Close commits before send's decision point | `Rejected(Closed, original packet)`; no admission. |
| S4 | Send commits before close | `Sent`; close preserves packet; receiver drains it or final teardown accounts for it. |
| S5 | Cancel commits before publication | `Cancelled(original packet)`; no receiver or teardown owns it. |
| S6 | Publication commits before cancel | `Sent`; no rollback or returned packet. Cancellation may stop waiting only through an ownership-resolving completion. |
| S7 | Cancel request and close race while send is pending | Exactly one `Cancelled(value)`, `Rejected(Closed,value)`, or `Sent` according to ordered commit points; never `Unknown` or two values. |
| R1 | Receive races final teardown on one queued packet | Exactly one receiver delivery or teardown disposition; the loser cannot access the slot. |
| R2 | Close races final receive of the last packet | Accepted packet can be delivered; EOF follows only after queue and prior publications are empty/resolved. |
| R3 | Final receiver handle is dropped while packets remain | Recovery or valid-context destruction accounts for each ID once; close alone is not disposal. |
| T1 | Spawn fails after capture preparation | Original task and every capture returned, or a specified partial-construction cleanup path; no child executes. |
| T2 | Spawn succeeds, then immediate cancellation request | Task retains captures until join/equivalent completion, including in-flight callbacks; release occurs once afterward. |
| T3 | Parent exits scope while child blocks or ignores cancellation | Scope cannot reclaim captured storage or complete until an approved join/completion policy is satisfied. |
| T4 | Destruction provider or payload is thread-affine | General channel/spawn rejects the type; future executor-bound cleanup must prove correct context. |
| A1 | Send/transfer uses incompatible allocator provider or provider expires | Reject before transfer or preserve the original provider's lifetime for eventual destruction; no cross-provider free. |
| A2 | Admission or stack reversal would allocate and allocation fails | Failed operation cannot lose or duplicate an owned packet. Specify whether allocation failure returns the packet or is a fatal trap before promising a nonblocking API. |

Tests S1–S6, R1–R3, and T1–T2 require both accepted and rejected static cases:
use-after-move, escaped borrow capture, thread-affine payload, incompatible
provider, and unsynchronized shared access must fail; valid transferable
payloads with completed local loans must pass once the language supplies the
missing cross-thread guarantees. Fault injection at each commit edge and a
small history checker are more informative than elapsed-time stress alone.

## Remaining specification decisions

1. Choose the final undelivered-message disposition and handle-lifetime model.
   A recovery object is more reversible than automatic destruction but needs a
   clear owner and drop policy itself.
2. Define the payload transfer/destruction relation, including recursive owned
   fields, provider lifetime, destructor context, and foreign handles. A
   blanket `Owned<T>` rule would be unsound.
3. Define the memory-order and linearization contract for publication, close,
   receive, cancellation acknowledgment, and teardown. Decide FIFO scope.
4. Define the result/completion handle when a cancellable send or spawn is
   abandoned, plus failure and partial-construction cleanup.
5. Define scoped task completion for blocked/uncooperative children and
   callbacks; cancellation request alone is insufficient.
6. Decide whether a future concurrent queue requires a true indexed ring for
   latency/throughput. The current two-stack FIFO establishes expressibility,
   not real-time or lock-free performance.

These decisions belong to a later concurrency specification. The first RM0
function-local stored-borrow slice does not depend on them.
