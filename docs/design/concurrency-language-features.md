# Candidate concurrency features and placement

**Design classification, not implementation authorization.** A = fundamental
language contract; B = compiler-supported abstraction; C = standard library;
D = optional syntax; E = premature as a language feature. A library may still
need a small trusted intrinsic or foreign primitive. The 36-workload mapping
is in [the analysis](concurrency-workload-analysis.md).

| Candidate | Class | Workload-grounded reason and boundary |
| --- | --- | --- |
| Move semantics/ownership transfer | **A — existing core** | `actor-buffer` and `payment-outbox` need a single owner across successful enqueue; Merit already moves owned values, but cross-thread commit/failure semantics are new. |
| Transfer/share safety constraints | **A — proposed** | `thread-per-core`, `immutable-tree`, and `ffi-callback` need separate transferability, safe concurrent sharing, and thread affinity; ownership alone does not imply any of them. Name/derivation rules remain open. |
| Data-race rule and memory/publication model | **A — proposed** | `locks-atomics`, `ring-buffer`, and `concurrent-map` need a defined happens-before and non-atomic race policy. A library cannot invent the compiler/optimizer's memory semantics. |
| Atomic load/store/CAS and ordering | **A primitive; C wrappers** | `lock-free-queue` needs compiler/backend-recognized atomic semantics; a tiny intrinsic boundary can support typed library atomics. Do not make every algorithm a keyword. |
| Safe FFI ownership, thread affinity and callback lifetime | **A boundary; C adapters** | `ffi-callback` can call C today, but retained cross-thread callbacks need compiler-enforced handle/escape rules plus a trusted adapter. |
| Borrow/capture validity across task scope | **A semantic rule; B checking** | `structured-tasks` requires a child to finish before borrowed parent storage is destroyed; local RM0 last-use alone does not prove this. |
| Effect/capability boundary for suspension or retry | **B** | `async-io` and `stm` need checker help to prevent unsafe suspension/retry with live resources or irreversible effects. Full effect syntax is undecided. |
| Scoped thread/task group | **B interface, C executor** | `structured-tasks` can use a library API if the compiler proves capture/send/lifetime and the runtime guarantees join or cancel-and-join. |
| Typed bounded channels | **C on A primitives** | `csp-pipeline` and `ring-buffer` need capacity, backpressure, close, and ownership-on-failure; no channel keyword is necessary. |
| Actor isolation and typed messages | **C first; B only if needed** | `actor-map` can be a single-owner task plus typed channel; compiler actor syntax only if library cannot preserve isolation or diagnostics. |
| Locks/RW locks/condition variables | **C on A primitives** | `concurrent-map` needs guard-based access, poisoning/fairness policy, and safe wrapper; lock order is a library/application concern. |
| Immutable data sharing | **A share-safety constraint; C structure** | `reporting` can share immutable versions if retention/reclamation is safe; persistent tree and atomic root are library designs. |
| Pattern matching/tagged unions | **A — existing core** | `actor-lifecycle` needs typed command/result variants; Merit already has enums/match for current surface. |
| Result/error propagation | **A — existing core** | `payment-outbox` needs explicit failure paths; Merit already has Result-style propagation, but async cancellation is new. |
| Cancellation and cleanup | **A safety obligation; C policy** | `structured-tasks` and `actor-buffer` require single destruction and owned-message disposition; cancellation token, deadline, retry policy belong in libraries. |
| Async/await and coroutine suspension | **B later** | `async-io` may justify state-machine lowering and suspension-aware borrows; thread-pool I/O can validate the need before new syntax. |
| Transactional state/STM | **E as built-in; C experiment** | `stm` requires retry-safe effects and conflict policy; a bounded library experiment should precede compiler transactions. |
| Deterministic scheduling hooks | **C test/runtime support** | `actor-lifecycle` and `trading` need seed, trace, and replay hooks; deterministic production scheduling is not a universal language guarantee. |
| RAII/defer-style cleanup | **A existing deterministic drops; D defer syntax** | `structured-tasks` needs cleanup on all exits; current drop rules are baseline, while a `defer` keyword is optional and may complicate cancellation semantics. |
| Explicit allocation/resource limits | **A existing capability; C budgets** | `csp-pipeline` and `fraud-stream` need bounded queues/windows; language keeps explicit allocation authority, libraries enforce capacities and quotas. |
| Work stealing, thread-per-core routing | **C** | `fork-join` and `trading` need different schedulers; a single built-in scheduler would constrain both. |
| Financial transactions/accounting syntax | **E as language feature; C/DB protocol** | `ledger`, `bank-transfer`, and `payroll` need durable isolation/idempotency beyond exact numerics; use libraries and storage systems. |

**Conditional classifications:** “A proposed” identifies a likely essential
semantic boundary, not a decision to implement it in RM0. “B” means a library
alone may be insufficient because the compiler must prove capture, suspension,
or effect properties. A proof that a safe library API and narrow primitives
cover those properties would move that candidate toward C. Conversely, a
counterexample where a safe API cannot be expressed should be recorded before
adding a keyword. Zero-copy message transfer is plausible for owned buffers,
but queue publication, allocator compatibility, pinning, and failed-send
ownership must be measured and specified; “zero cost” is not assumed.
