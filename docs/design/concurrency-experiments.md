# Prioritized concurrency design experiments

The first bounded sensor pipeline probe is documented in
[sensor-pipeline-experiment.md](sensor-pipeline-experiment.md). Its sequential
and single-threaded stages are current-language examples; its SPSC and
three-stage concurrent cases remain plans.

**Plans, not executed tests.** Pseudo-Merit notation is proposed. No compiler
or runtime implementation is authorized by this document. All experiments
first compare with a sequential oracle or history checker, then measure on
declared hardware, input distribution, worker count, and resource limit.
Negative tests identify desired compile-time rejection only after the
corresponding future feature is specified. Distinguish safety failures from
application-protocol failures and record a reproducible schedule/fault trace.

| Priority / catalog cases | Hypothesis and competing approaches; minimal proposed example | Positive and negative evidence | Runtime/stress and metrics; expected distinguishing result; falsifier |
| --- | --- | --- | --- |
| 1. `borrow-last-use` | F+A local loan versus lexical B: `let r=borrow x; read(r); mutate(x)` | **Accept** after proven final use; **reject** `mutate(x); read(r)`; safely reject branch alias with unproven origin. | Compile time, diagnostics, canonical MIR bytes, oracle/native parity. A must accept first example; if source identity or cleanup changes, narrow RM0. |
| 2. `structured-tasks` | Scoped library API plus compiler capture check versus unscoped spawn: `scope { spawn(borrow x); join_all() }` | Future **accept** proven join-before-drop; **reject** escaped child retaining x. | Cancel sibling at allocation and during join; live tasks/drop count/cancellation latency. If library scope cannot enforce join on every exit, compiler support is needed. |
| 3. `actor-buffer`, `csp-pipeline` | Move-only bounded channel versus copy-on-send: `send(move b)` | Future **accept** transferable b; **reject** use-after-send and borrowed escape; failed send returns ownership or destroys once. | Race full queue/cancel/receiver death; bytes copied, allocations, throughput, drop count. Zero-copy claim falsified by measured hidden copy or allocator mismatch. |
| 4. `locks-atomics`, `ring-buffer` | Typed atomic primitive + library lock/channel versus opaque C wrapper: `atomic_store(flag,1,Release)` | Future **accept** publish/acquire protocol; **reject** unsynchronized conflicting ordinary accesses and invalid ordering combination. | Weak-memory litmus, capacity-one wrap; retry/fairness/latency. If safe library cannot express publication without unchecked FFI, primitive boundary is necessary. |
| 5. `immutable-tree`, `reporting` | Retained immutable snapshot versus copied snapshot: `publish(move root); read(snapshot)` | Future **accept** share-safe retained root; **reject** mutable alias or early free. | Publish/abandon versions with stalled readers; peak retained memory, update allocations, read throughput. If retention requires pervasive hidden costs, reconsider model. |
| 6. `fork-join`, `matrix-multiply`, `tensor-alias` | Disjoint partition proof versus copy/lock fallback: `parallel_for(tiles_mut(out))` | Future **accept** proven disjoint tiles; **reject** overlapping/overflowed strides; safely reject ambiguous alias. | Exact integer oracle and declared FP tolerance; speedup, cache misses, copy bytes. If proof cost outweighs copying on useful sizes, library fallback may win. |
| 7. `ffi-callback` | Scoped registration handle versus raw callback pointer: `register_scoped(borrow state)` | Future **accept** only with unregister+drain and affinity proof; **reject** callback after scope or wrong-thread release. | Race unregister/free/reentrancy; in-flight count, leak count, latency. If C API lacks drain guarantee, safe wrapper must reject or own state independently. |
| 8. `bank-actor`, `bank-transfer`, `ledger` | Account actors alone versus serializable storage transaction: `transfer(a,b,Money)` | **Accept** valid balanced transfer under declared transaction; **reject** overdraft/unbalanced/overflow, not necessarily at compile time. | Opposing transfers and crash at commit; serializability/history, conservation, committed TPS, conflict/lock waits. If actor-only history violates invariants, no actor language feature fixes it. |
| 9. `payment-outbox`, `invoice-saga` | Durable outbox+idempotency versus direct send: `commit(payment,outbox)` | **Accept** same key/same payload retry; **reject** same key/different payload; test is protocol-level. | Crash after commit/before response and after send; effect count, duplicate delivery, lag. If duplicates cause double charge, idempotency contract fails. |
| 10. `trading`, `audit-replay`, `fraud-stream` | Single-writer versioned log versus nondeterministic shared updates: `apply(sequence,event)` | **Accept** ordered valid event; **reject** gap, duplicate sequence, policy mismatch; library/protocol validation. | Randomized recorded scheduling, restart/replay; equality of balances/hash, p99/p999 latency, gaps. If replay differs at fixed inputs/policy, deterministic-execution claim fails. |
| 11. `async-io`, `structured-tasks` | Thread-pool I/O library versus compiler coroutine lowering: `await read(borrow buf)` | Future **accept** only with proven buffer lifetime and cancellation; **reject** drop during in-flight read or unjoined task. | Short reads, timeout/completion race, CPU starvation; p99, scheduler delay, resource count. If pool meets workload without unsafe borrow crossings, defer `async` syntax. |

Experiments 1–4 test the smallest common safety boundary. Experiments 5–7
probe future sharing, views, and FFI without requiring their adoption. The
financial experiments distinguish memory/data-race safety from atomicity,
isolation, durability, and idempotency. A benchmark alone cannot prove any of
those contracts; pair stress with explicit sequential history, failure
injection, and source-level negative examples. A safe example a prototype
rejects is evidence about acceptance/ergonomics, not automatically unsoundness.
