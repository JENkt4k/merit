# Concurrency execution models: design comparison

**Status:** Architectural hypotheses, not Merit semantics. The 36 source
workloads are classified in [the catalog matrix](concurrency-workload-analysis.md).
Merit currently provides no concurrency runtime. Actor, channel, lock, and
task examples below describe possible libraries and future static boundaries.

| Model | Best-fitting workloads | Safety and correctness boundary | Fundamental versus implementation cost | Determinism, ergonomics, composition, FFI |
| --- | --- | --- | --- | --- |
| Actor/message passing | Actor lifecycle/map/buffer, account shards, ECS | Exclusive state owner and typed message transfer prevent shared mutation; reply order, delivery, restart, and cross-actor commit remain protocols. | Mailbox synchronization and queueing are inherent; copies, scheduler overhead, and per-actor memory depend on implementation. | Log input/order for replay; simple state isolation, but cross-actor transactions are hard. C callbacks need registration lifetime and affinity. |
| CSP/bounded channels | Streaming pipeline, fraud stream, ring buffer | Move-safe send and bounded capacity; close, blocked send, and cancellation decide who retains a payload. | Publication synchronization and backpressure are inherent; allocation and wakeup cost depend on topology. | Record send/receive order; stages compose, but cycles can deadlock. C producer needs ownership adapter. |
| Shared memory with locks/atomics | Map, B-tree, counter, lock-free queue | A guard/atomic protocol prevents races; logical linearizability and reclamation need separate proof. | Contention and cache coherence are inherent; lock granularity/CAS retries vary. | Schedule-dependent results unless operation order specified; flexible FFI, high audit burden. |
| Scoped tasks and fork/join | Merge sort, matrix tiles, BFS, reporting | Child lifetime within scope; moved or safely borrowed captures; join/cancel cleanup. | Task creation/synchronization inherent; grain, stealing, and worker count tunable. | Deterministic results for pure/disjoint partitions; library combinators can hide scheduling. Foreign work must honor join/cancel. |
| Immutable snapshots | Reporting, persistent tree, audit | Readers see one version; retention/reclamation prevents dangling roots. | Version retention/updates cost memory; copy versus structural sharing is optional. | Strong replay story with version IDs; simple readers, but publication/reclamation need explicit contract. |
| STM | In-memory multi-location update | Serializable commit and effect-free retry are needed; unsafe I/O during retry must be prevented. | Conflict tracking/retry work inherent; algorithm and abort rate vary. | Replay needs conflict/commit log; composition appealing but side effects and FFI troublesome. Defer. |
| Thread-per-core single writer | Trading, hot-key shards | Each partition owns mutable state; cross-core message ordering and transfer remain explicit. | Hops/NUMA and queueing inherent; batching and placement tunable. | Per-shard replay feasible; migration and cross-shard operations add protocol complexity. |
| Durable distributed workflow/DB | Ledger, transfers, outbox, saga | Transaction atomicity/isolation/durability and idempotency are not memory-safety guarantees. | Network/durable writes are inherent; consensus/2PC/saga policy varies. | Versioned event log and idempotency key enable replay; C/DB APIs need safe ownership wrappers. |

No universal optimum follows from the catalog. Actors reduce sharing but cannot
make a two-account transfer atomic; locks can serialize memory but cannot make
a disk write durable; pure fork/join helps numeric algorithms but not a
timeout-after-payment ambiguity. These are design deductions from each
workload's contract, not benchmark results.

## Comparative reference points

- [Rust `Send`](https://doc.rust-lang.org/std/marker/trait.Send.html),
  [`Sync`](https://doc.rust-lang.org/core/marker/trait.Sync.html), and
  [scoped threads](https://doc.rust-lang.org/std/thread/fn.scope.html) show
  separate transfer, sharing, and bounded child lifetime contracts. Merit need
  not copy their syntax or trait implementation.
- The [Go memory model](https://go.dev/ref/mem) makes publication and
  happens-before obligations explicit for channels, locks, and atomics. Go's
  guarantees for racy programs are not a substitute for Merit's proposed
  compiler-enforced data-race freedom.
- [Erlang processes](https://www.erlang.org/doc/system/ref_man_processes.html)
  demonstrate supervision/message isolation, while the catalog's restart and
  committed-effect cases still require application protocols.
- [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html) shows why
  durability and crash atomicity require a storage protocol beyond a language
  ownership rule.
- The [C++ Core Guidelines on concurrency](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#cp-concurrency-and-parallelism)
  and C/C++ atomic/FFI practice expose low-level performance choices; their
  complexity argues for a narrow, well-specified unsafe/atomic boundary before
  any lock-free standard library. This is a design inference, not measured
  Merit performance.

## Measurement discipline

For each competing implementation, state identical input, hardware, worker
count, memory limit, ordering/consistency level, and fault model. First check
sequential-history or domain oracles and cleanup. Then collect p50/p99 latency,
throughput, peak memory, bytes copied, allocations, queue occupancy, retries,
contention, and tail fairness as relevant. A speedup without equal correctness
is not evidence for a language feature. Reproducible builds and deterministic
results are different properties: parallel scheduling can vary while canonical
compiler artifacts remain byte-stable.
