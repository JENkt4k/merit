# Provisional channel and task ownership lifecycle

**Status:** Owner-approved design directions for investigation, not an RM0
freeze, language specification, syntax proposal, or implementation authority.
All programs and API names below are **pseudocode**. Current Merit has no
threads, channels, cancellable send, or task spawn. The current single-threaded
sensor evidence is in [the sensor experiment](sensor-pipeline-experiment.md).

## Relationship to RM0

F separates resource validity, read/write access permission, and
transfer/destruction authority. A-style inferred final-use spans can prove that
a *function-local* immutable borrow no longer blocks a later owner operation.
They cannot prove that a value, its owned fields, allocator/release provider,
or destructor is safe on another execution context. A cancellation request is
not a final use or a transfer reversal. The first RM0 stored-borrow slice
therefore remains local and unchanged; all cross-thread properties here belong
to a later concurrency milestone. Do not derive transferability,
shareability, affinity, or destruction-provider compatibility from `Owned<T>`.

The provisional rules apply to ordinary in-process operation and cooperative
shutdown. Process termination, power loss, and external side effects are not
covered by exact-once cleanup. No new MIR, ABI, serialization, or diagnostic
contract is implied.

## Minimal proposed contracts

`try_send(value: T) -> Sent | Rejected { reason: Full | Closed, value: T }`
consumes its input binding on call. A rejection returns that **same** owned
value; it never drops it implicitly. A successful publication transfers
ownership to the channel at one linearization point. Before that point, the
operation temporarily holds the value; the caller cannot access it. A future
cancellable send must report exactly one of `Cancelled { value: T }`,
`Rejected { reason, value: T }`, or `Sent`. A cancellation *request* is not a
result and does not reclaim a published message. A full or closed nonblocking
send has no waiting phase; cancellation matters only if a future operation can
be pending or cancellation races its publication.

Close is a linearizable transition that prevents later admission. Accepted
messages remain in FIFO order and receivers may drain them. Once the queue is
empty and closed, receive reports end-of-stream. The exact ordering between
an already pending publication and close is decided by their linearization
order. End-of-stream additionally requires that earlier admitted/pending
publications are resolved; a temporarily empty closed queue cannot report EOF
while an earlier successful publication is still becoming visible. Closing does
not dispose of queued values. Final teardown must account
for each undelivered value once, by draining, returning it through an explicit
recovery path, or destroying it with a valid release provider on an allowed
execution context. The choice and handle-lifetime rules remain open.

`spawn(task_with_captures) -> Spawned(handle) | SpawnFailed(task_with_captures)`
has the same ownership split: failure returns the original task and captures;
success transfers them to the task. A cancellation request cannot free captures
while the task or callbacks may access them. Join, or an equivalent proven
completion barrier including callbacks, precedes reclamation. Failure to start
and failure to complete are different outcomes.

## Ownership state machine

The states describe one noncopyable message. `Published` and `Received` each
have one owner, never a second caller owner. Every return or terminal cleanup
consumes the preceding state exactly once.

| State | Event and next state | Sole authority / observable result |
| --- | --- | --- |
| CallerOwned | Begin send -> InOperation | Operation holds value; caller binding is unavailable. |
| InOperation | Full or closed -> CallerOwned | `Rejected(reason, original value)`; no drop. |
| InOperation | Cancellation wins -> CallerOwned | `Cancelled(original value)`; no publication or drop. |
| InOperation | Publication wins -> Published | `Sent`; channel owns value. Cancellation cannot roll this back. |
| Published | Receive wins -> ReceiverOwned | Receiver obtains value; channel slot is empty. |
| Published | Close -> Published | Queue retains value; receiver may still drain it. |
| Published | Final teardown -> Recovered or Destroyed | One explicit recovery or one valid destruction; no leak or second drop. |
| ReceiverOwned / Recovered / CallerOwned | Owner moves or drops -> Transferred / Destroyed | Ordinary ownership rules and exactly-once cleanup. |

Close and publication, cancellation and publication, receive and teardown, and
failed send and close each need one linearization order. If cancellation wins
before publication, it returns the value; if publication wins, cancellation
can only report the committed result. A result must resolve ownership even if
the caller stopped waiting. A channel cannot silently leave a message in an
unobservable "maybe sent" state. Destructors may run only after all accesses
and permitted callbacks finish, using the original resource's compatible
allocator/release provider.

For a task with captures, replace `InOperation` with `SpawnPending`,
`Published` with `TaskOwned`, and `Received` with `Joined/Completed`. Spawn
failure returns all captures. Successful spawn makes them unavailable to the
caller. Cancellation requests do not change `TaskOwned`; completion and join
do. Captures are released once after completion, including callback quiescence.

## Minimal accepted and rejected specifications

These are future **specification cases**, not currently executable Merit tests.
`packet()` has an owned payload, destructor counter, and release-provider ID.
Each case checks that the original provider performs any final release.

| Case | Proposed result / invariant |
| --- | --- |
| Accept: send into available slot, then receive | `Sent`; sender cannot reuse packet; receiver gets original identity and releases it once. |
| Accept: full or closed `try_send(packet)` | Typed `Rejected` returns original identity; caller may retry or drop exactly once; channel never destroys it. |
| Accept: close with queued packets, then receive | Existing messages drain in order; the next receive reports end-of-stream. |
| Accept: cancel beats publication | `Cancelled(packet)` returns original identity; no receiver observes it. |
| Accept: publication beats cancel | `Sent` remains committed; receiver or teardown accounts for packet once. |
| Accept: spawn fails / succeeds | Failure returns task and every capture; success gives task ownership and join precedes capture destruction. |
| Reject: sender uses packet after starting send, or after `Sent` | A moved binding cannot provide a second owner, even if cancellation was requested. |
| Reject: returned failure lacks payload, or return and queue both own it | No implicit rejected-message drop, leak, or duplicate authority. |
| Reject: nontransferable or thread-affine payload sent to general channel | A destructor or provider may be called on an invalid context. |
| Reject: escaped borrow captured by task, or capture released after cancel request before join | Local inferred loan span does not prove task or callback completion. |

Stress/history tests must force cancellation at each send/close publication
boundary, receive versus final teardown, failed spawn versus capture cleanup,
and child completion versus cancellation. Record operation histories, message
identities, allocator IDs, destructor counts, and callback lifetimes. Exactly
one result and one terminal owner must be explainable for each history. A
timeout or cancellation request alone cannot be treated as completion.

## Library-only limits and remaining approvals

A trusted channel library cannot establish safe cross-thread use from current
`Owned<T>` alone. It needs compiler-enforced or otherwise soundly certified
transferability, concurrent shareability where applicable, thread affinity,
and destructor/provider compatibility; a specified atomic publication and
happens-before boundary; and scoped task/capture lifetime enforcement. A safe
library may implement channel policy and queue mechanics on top of those
guarantees. A general owned ring is not yet demonstrated with current
`vec_get` (copying owned elements is rejected) and `vec_pop` (tail only); safe
occupied-slot take for a true indexed ring requires separate proof. A focused
single-threaded two-stack FIFO probe now establishes a bounded library
alternative with typed return-of-value failure, without proving a concurrent
channel. See the [follow-up evidence audit](concurrency-evidence-audit.md).
The `Vec<Sample>` replacement-compiler limitation is a separate
compiler coverage issue, not evidence for or against these ownership rules.

Human decisions still needed before a concurrency specification:

1. On final teardown, do undelivered messages drain, return through a recovery
   object, or get destroyed? Who can initiate teardown, and what if receivers
   or senders still hold handles?
2. What exact execution contexts may run destructors and release providers?
   What bounds the initial transferable payload set and allocator lifetime?
3. What memory model, atomic primitive, and linearization point establish
   publication and close ordering? Is FIFO guaranteed only per sender/channel?
4. How does an abandoned cancellable-send result return or dispose of an
   untransferred value without a leak? How are blocked senders awakened on
   close?
5. What join/completion guarantee covers blocked or uncooperative tasks and
   in-flight callbacks? Where are failed-spawn task objects destroyed if the
   caller declines to retry?

None of these questions closes RM0 or authorizes concurrency implementation.
