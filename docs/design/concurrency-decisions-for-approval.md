# Concurrency architecture: decisions for human review

**Recommendation only.** No concurrency semantics, runtime, syntax, MIR/ABI
encoding, or RM0 decision is approved by this review. The RM0 borrowing
direction in `docs/design/alpha3/BORROW_MODEL_DECISION.md` remains preferred
but unfrozen. The 36 catalog workloads are requirements to investigate, not
proof that a feature belongs in the language.

## Proposed smallest coherent foundation

1. Keep exclusive ownership transfer as the baseline. Define *separate*
   transferability, concurrent shareability, and thread-affinity properties;
   do not infer them from `Owned`, immutability spelling, or a local borrow.
2. Specify a data-race and publication/happens-before model plus a narrow
   typed atomic/synchronization primitive boundary before exposing threads.
3. Define scoped child lifetime and cancellation ownership so a child cannot
   outlive captured storage and every resource is destroyed once.
4. Build typed bounded channels, scoped task groups, actor adapters, and
   thread-per-core executors as **libraries** over those primitives first.
   Require evidence before adding actor/channel keywords or a universal
   scheduler.

This is a proposed **post-RM0 concurrency design milestone**, not the next
compiler implementation task. RM0's immutable function-local borrow slice
does not need threads, and its non-lexical final-use acceptance must not be
silently extended across thread or async boundaries. [RM0 implications](rm0-concurrency-implications.md)

## Questions requiring approval before a concurrency specification

| Decision | Recommended direction | Evidence or counterexample needed |
| --- | --- | --- |
| Transfer and share traits | Distinct transfer-safe, share-safe, and thread-affine properties; derivation must account for owned fields, allocators, foreign handles, and custom destructors. | `actor-buffer`, `immutable-tree`, `ffi-callback`; prove no unsound auto-derivation. |
| Memory model | Race-free safe code with explicit publication; atomic orderings only through typed primitives/trusted wrappers. | `ring-buffer` weak-memory litmus and `locks-atomics` multi-field snapshot. |
| Scoped task semantics | All child tasks joined or cancel-and-joined before scope exit; specify blocked/uncooperative child behavior. | `structured-tasks` cancellation and resource accounting. |
| Channel ownership | Define exact send linearization point, capacity, close, failure/cancel return of ownership, and ordering scope. | `actor-buffer` and `csp-pipeline` fault injection. |
| Sharing and reclamation | Choose when immutable readers can retain an object, release order, and safe reclamation; do not implicitly adopt reference counting. | `immutable-tree`, `concurrent-map`, `reporting`; compare copy/RC/epoch. |
| Borrow/capture across concurrency | Defer until task scope, origin, suspension, and escape proofs exist. Local RM0 final-use is insufficient. | `structured-tasks`, `async-io`, `ffi-callback` accept/reject pairs. |
| FFI boundary | Declare callback lifetime, thread affinity, release provider, and foreign failure behavior at safe adapter boundary. | Race unregister/free and wrong-thread callbacks. |
| Resource limits and scheduling | Library-level explicit capacities, quotas, scheduler choice, and test trace/replay hooks. | Compare actor/CSP/fork-join/thread-per-core under equal workloads. |
| Financial transactions | Keep in DB/storage and domain libraries with exact Merit numeric semantics; no built-in accounting or transaction syntax initially. | `ledger`, `bank-transfer`, `payment-outbox` crash and history tests. |

## What this review finds missing

The critical missing capability is **safe cross-thread ownership and sharing
authority with a specified publication rule**. Next are scoped child cleanup,
atomic primitives, explicit cancellation/failed-send ownership, safe foreign
callback lifetime, and eventually disjoint mutable views. Actors and channels
can be built on these; they do not by themselves solve data races in unsafe
wrappers or distributed transaction correctness. An isolated immutable tree
or exact decimal is insufficient to prove safe concurrent publication.

## Defer until an experiment demonstrates need

Built-in actor syntax, universal async/await, built-in STM, lock-free
collections, automatic Shared/Weak, tensor syntax, GPU execution, transparent
distributed transactions, and deterministic production scheduling. A narrow
library-first implementation may still later justify compiler-supported
lowering; record the failing library-only case and measurements before doing so.

## Approval boundary

Reviewers should first approve or revise the **architectural questions**, not
authorize implementation. The next action after approval is a bounded semantic
specification with accepted/rejected programs, memory-order and cleanup traces,
MIR/ABI versioning, differential tests, and explicit runtime responsibilities.
The [experiments](concurrency-experiments.md) identify evidence that could
falsify the recommendations. No RM0 checkbox is closed by this document.
