# Bounded sensor pipeline: RM0 concurrency probe

**Status:** Stages 1–2 are a current-language, single-threaded experiment in
`examples/projects/sensor_pipeline`; stages 3–4 are design-only pseudocode.
This does not freeze RM0, add concurrency syntax, or claim a real-time control
guarantee. The first two stages intentionally separate a copyable `Sample`
from an owned `Buffer` payload: a copyable sample alone cannot test move safety.

## Capability matrix

| Stage | What current Merit supports | Missing language boundary | Library/runtime boundary | Verification |
| --- | --- | --- | --- | --- |
| 1. Sequential producer → consumer | `Sample { sequence:u64, distance_mm:i32 }`, typed function call, exact integer arithmetic, explicit printing. `consume(borrow sample:Sample)` uses current call-scoped borrow. | None for this example; no stored reference is needed. | Sensor acquisition, clock and physical-unit validation are outside the language. | Direct call prints 120; interpreter/native parity. |
| 2. Single-threaded bounded ring | `Vec<Sample>` prefilled to capacity three, head/tail/count, checked `vec_set`/`vec_get`, explicit allocation capability. A separate capacity-one `Vec<OwnedSample>` moves a `Buffer` in and out; a full send destroys the transferred packet once. | A general owned-element ring needs a safe arbitrary-slot take/empty-slot contract; current `Vec<OwnedSample>` supports push/pop but does not itself provide an indexed owned take. | Queue full/empty policy, stale-sample policy and capacity are library/application rules. | Fill/full/wrap/drain/empty order, owned move rejection, full-send disposition, capability rejection. |
| 3. Two-thread SPSC queue | Current single-thread state and move rules are useful but do not authorize cross-thread access. | Transfer/share safety, thread affinity, publication/happens-before, atomic ordering, child lifetime and cancellation ownership are not specified. | Bounded SPSC queue and scheduler can be library/runtime features after the language boundary is frozen. | Future weak-memory litmus, lost/duplicate sequence history, failed-send ownership and race stress. |
| 4. Sensor → filter → control | Structs, calls, and sequential processing exist; concurrency does not. | Same stage-3 boundary plus safe task/channel lifetime, capture/escape checks, and possibly future async suspension rules. | Two bounded channels, filtering, control policy, cancellation and backpressure are library/application responsibilities. | Future per-stage order, end-to-end sequence/freshness, faults at every handoff, bounded memory and cleanup. |

The example's output is a deterministic trace, not a physical sensor or motor
controller. It uses `u64` for sequence and `i32` for distance; the application
must reject invalid distance ranges and define sequence overflow/wrap behavior
before deployment. Ring indices are `i64` and wrap only at the fixed positive
capacity. The example does not exercise untrusted sensor input or sequence
overflow; those are explicit later tests.

## Minimal programs and ownership points

Actual stage-1/2 Merit is in the linked example. Its core operations are:

```merit
struct Sample { sequence: u64; distance_mm: i32; }
fn consume(borrow sample: Sample) -> i32 { return sample.distance_mm; }
// The sample ring has fixed slots and a separate count, head and tail.
// ring_push returns 0 on full without modifying the ring.
// ring_pop returns 0 on empty without modifying the output.
```

`Sample` is copyable, so `ring_push` copies fields and does **not** prove owned
message transfer. The separate `OwnedSample { sample:Sample, payload:Buffer }`
is passed by value to `owned_slot_send` and popped out. A full send explicitly
drops its transferred packet and reports rejection; the caller cannot reuse
that packet. `OwnedSample`'s destructor prints the sequence: the rejected
packet prints `7` once, and the received packet prints `6` once at its explicit
drop. Using the old binding after send is a compile error. This is a
capacity-one owned handoff, **not** a
general multi-slot owned ring; that gap is a finding, not an API claim.
The current checker required the success path to be written as an explicit
`else` after the full-path `drop(item); return`: placing the push after that
`if` was diagnosed as use of dropped `item`. The explicit branch version
passes parity. This is evidence of a current path-sensitive ownership limit,
not approval to change the checker in this experiment.

The following is **proposed pseudocode**, not Merit syntax:

```text
// Stage 3, future only:
scope workers {
    queue = spsc<OwnedSample>(capacity = 3)
    producer.send(move packet)  // success transfers ownership
    consumer.receive()          // receives one owner
}

// Stage 4, future only:
sensor --bounded_channel--> filter --bounded_channel--> control
```

On a failed enqueue, a future API must specify whether the packet returns to
the sender or is destroyed; neither outcome may duplicate or leak it. On
cancellation, distinguish before-publication from after-publication ownership.
Closing a channel must define what happens to queued packets and blocked
senders. The control stage must define whether it processes every sample,
discards stale samples, or uses the newest; FIFO order alone does not imply
freshness or a deadline.

## Safety and RM0 analysis

| Property | Stages 1–2 | Stages 3–4, still open |
| --- | --- | --- |
| Memory safety and cleanup | Current checker forbids use after the owned packet moves; vector and packet are explicitly dropped once. | A transfer-safe message type, publication boundary, in-flight ownership and join/cancel cleanup must be specified. |
| Race freedom | Trivial because there is one thread. | SPSC atomic indices and ordinary payload accesses need a memory model. `Owned` alone does not establish thread safety. |
| Ordering and backpressure | Head/tail/count preserve FIFO for copyable samples; full returns zero and does not overwrite. | Specify send linearization, per-channel ordering, bounded blocking or rejection, and end-to-end stage order. |
| Overflow | Fixed ring indices wrap at capacity; sequence and distance policy is not exercised. | Specify sequence wrap, bounded queue counters and timestamps, plus checked numeric operations. |
| RM0 F/A/B | Existing call-scoped borrow is valid. A and B make no difference because no stored reference is used. | F's authority split is useful vocabulary, but A-style local last-use does not prove `Send`, `Sync`, publication, or an escaping task capture. B would also reject unsupported cross-thread references. |

For a **future local stored-borrow** variant, `let r=borrow sample; read(r);
move(sample)` is required acceptance under the proposed F+A straight-line
minimum only if the final use and provenance are proven. The same move before
`read(r)` must fail. B's lexical restriction would reject the safe post-last-use
move inside the same scope. This is hypothetical and not executed here.

Conceptually, C can implement all four stages with explicit structs and C11
atomics but leaves move/alias safety and cleanup to discipline; Rust can use
`Send`/`Sync`, scoped threads, and ownership-aware channels with explicit
atomic rules for a custom SPSC queue; Erlang processes naturally isolate
sensor/filter/control state but may copy or retain messages and still need a
freshness/deadline and overload policy. These are design comparisons, not
Merit performance measurements. See [Rust scoped threads](https://doc.rust-lang.org/std/thread/fn.scope.html),
[Rust `Sync`](https://doc.rust-lang.org/core/marker/trait.Sync.html), and the
[Go memory model](https://go.dev/ref/mem) for relevant lifetime and
publication contracts.

## Focused evidence and proposed next tests

`tests/test_epoch_iii_vec.py` passed **49/49** before editing. The new
`tests/project/test_sensor_pipeline.py` passed **3/3** after the example was
added: reference/native output parity and exact trace, compile-fail use after
owned handoff, and compile-fail allocation without capability. Both
runs used MSYS2 UCRT64 GCC and D: temporary paths. The example also passed
`merit.project.cli verify` with output matching in 50 bytes. No broad gate was
run for this isolated example. No stage-3/4 program was compiled.

Next focused tests, before any concurrent implementation, should cover ring
capacity one and zero, invalid/maximum sequence, untrusted negative distance,
stale-sample policy, arbitrary owned-slot take, and cancellation disposition.
Only a later approved concurrency milestone would add compiler-fail tests for
non-transferable payloads, escaped borrowed captures, or invalid atomic access,
plus SPSC stress/history and memory-order litmus tests.

## Questions requiring human approval

1. Is the **capacity-one owned handoff plus copyable multi-slot ring** enough
   evidence for this stage, or should a future library primitive support
   arbitrary indexed owned take before stage 3?
2. What are the sensor input bounds, sequence-wrap behavior and stale-sample
   policy? These are application contracts, not automatic language semantics.
3. Which failed-send and cancellation outcome owns a packet? Where is the
   publication/linearization point?
4. What transfer/share and scoped-child guarantees must be frozen before a
   two-thread SPSC example can be considered safe Merit?

No answer here authorizes concurrency implementation or changes RM0's open
status. Stages 3–4 remain conceptual.
