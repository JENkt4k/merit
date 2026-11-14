# Alpha.3 Resource Model — RM0 Design Ledger

## Status and authority

RM0 is the completed **design and semantic-freeze** milestone after the SH0–SH6
self-hosting campaign closed in PR #135. The existing
`docs/design/MEMORY_RESOURCE_MODEL.md` is an input proposal, not a language
specification. This ledger tracks decisions that must become precise before any
Alpha.3 resource feature is implemented. Unresolved entries grant no syntax,
runtime, ABI, or compiler behavior.

The Alpha.2 ownership and borrowing rules in `spec/OWNERSHIP.md`, plus their
diagnostics, MIR/protocol encoding, generated C, layout, and runtime behavior,
remain the implemented contract. Self-hosting and the independent Python oracle
remain intact. RM0 changes documentation and executable design examples only;
it does not change compiler code or production semantics.

## Bounded outcome

Produce one reviewed, versioned semantic contract for the **first** Alpha.3
resource-model implementation slice. It must name the supported relationship,
the authority to access and mutate it, its lifetime and destruction rules,
observable failure behavior, and every representation boundary it crosses.
The contract may explicitly defer relationships whose rules are not yet sound.
No implementation milestone begins from a merely suggestive example in the
proposal.

RM0 is not an implementation of stored borrows, `Shared`, `Weak`, regions,
pinning, foreign ownership, tensors, concurrency, or new resource syntax.
Choosing which of those to specify first is part of RM0. Separate compilation
and dependency-granular caching are also outside this milestone.

## Existing invariants to preserve

| Alpha.2 behavior | RM0 compatibility obligation |
| --- | --- |
| Owned values transfer by move, never implicit copy | New relationship forms cannot reinterpret existing owned bindings or moves. |
| `borrow` and `borrow_mut` are call-scoped, with validated ephemeral returned-borrow propagation | Existing accepted and rejected programs retain their results and diagnostics; any stored-borrow form requires an explicit new contract. |
| `drop`, `replace`, implicit cleanup, early return, and destructor order are deterministic | New cleanup rules must specify order, single destruction, and failure paths without changing current traces. |
| Allocation and hazardous operations require lexical capability authority | New runtime mechanisms identify their required authority and visible costs. |
| Interpreter/native execution, canonical MIR, protocol, generated C/header, layout, and diagnostics are compared independently | Any future encoding or ABI change is versioned and has byte-level or differential evidence. |

Semantic ownership, allocation strategy, mutation authority, and address
stability are separate dimensions. The current MIR/resource-effect representation
is valid for the Alpha.2 subset; it is not evidence that all later resources are
exclusive, all borrows are permanently call-scoped, or pinning follows ownership.
The SH3 deferred seams in `SELF_HOSTING.md` are the starting architecture audit.

## Finite decision matrix

`OPEN` means no Alpha.3 behavior is authorized. `FROZEN FOR RM1` records the
reviewed first-slice contract merged in PR #140. `DEFERRED` excludes the relationship
from the first slice without freezing its later semantics. A row closes only with a
normative rule, accepted and rejected examples, observable behavior, and a
compatibility/evidence entry. Rows marked deferred still need an explicit
boundary explaining why the first implementation slice does not depend on them.

| ID | Decision to freeze | Proposal anchor | State |
| --- | --- | --- | --- |
| R1 | First implementation slice and whether relationship names are conceptual or user syntax | §§4, 28–30, 33 | FROZEN FOR RM1: immutable function-local reference mode; preferred provisional spelling with old-grammar compatibility. |
| R2 | Borrow validity, storage and escape, access/mutation authority, alias conflicts, and inference versus named lifetime syntax | §§4.2, 8, 30 | FROZEN FOR RM1: F authority split, A-style final use, stated minimum accepted/rejected cases. |
| R3 | Resource ownership versus allocator identity, transfer, and deterministic normal/early/error cleanup | §§4.1, 6–7, 15, 30 | FROZEN FOR RM1: owner retains cleanup; no borrow destructor, allocation, or RC. |
| R4 | Shared/weak identity, clone and release, cycles, upgrade failure, runtime costs, and whether RC is semantic or implementation detail | §§4.3–5, 30 | DEFERRED: independent future semantic contract. |
| R5 | Region membership, escape, destruction order, and interaction with owned/borrowed values | §§6, 30 | DEFERRED: local borrow has no region membership. |
| R6 | Address stability/pinning and its relation to moves, borrows, and FFI | §§11, 18, 30 | DEFERRED: live local reference validity does not imply public pinning. |
| R7 | Foreign ownership/retained callbacks, hazardous capability boundaries, and unwind/fatal behavior | §§11–13, 30 | DEFERRED: no foreign retention/callback right. |
| R8 | Arrays/views and overlap authority; concurrency and thread transfer boundary | §§9–10, 30 | DEFERRED: no aggregate view, concurrency, or thread-transfer right. |
| R9 | Canonical MIR effects, diagnostics, serialization/versioning, C ABI/layout, interpreter/native and stage equivalence | §§21, 26–27 and SH3 deferred seams | FROZEN FOR RM1: conditional HIR v1/v2, MIR v1/v2, native v4/v5; exact old bytes, old-reader rejection, diagnostics, framing, and migration evidence specified. |

## Required evidence before semantic freeze

1. Record the source contract for each chosen rule and a decision record for
   every matrix row, including explicit deferral where applicable.
2. Give accepted and rejected minimal programs for move, borrow escape,
   alias/mutation conflicts, cleanup, capability use, and every selected new
   relationship. Specify diagnostic identity and source location expectations.
3. Define traces for normal return, early return, error propagation, and
   destructor/finalization; identify which outcomes are observable and which
   remain implementation details.
4. Map each selected rule through checker, canonical MIR resource effects,
   interpreter, deterministic C, runtime, public header/ABI, protocol, and
   Python oracle. Identify versioned changes before implementation.
5. State the cross-stage and cross-platform differential tests needed for the
   later implementation. Existing Alpha.2 fixtures must continue to pass.
6. Review the SH3 architectural seams against the selected model. Record any
   redesign as later implementation work; do not introduce speculative
   abstractions during RM0.

## Ordered RM0 work

PRs #138 and #139 completed a bounded concurrency design probe. Their
channel/task directions remain provisional future constraints, not RM0
resource semantics or implementation authority. The preferred first slice is
still immutable function-local stored borrows under F with A-style final-use
proof. The [implementation readiness audit](docs/design/alpha3/LOCAL_BORROW_IMPLEMENTATION_PLAN.md)
records the minimum acceptance/rejection matrix, compiler boundaries, tests,
and the compiler evidence requirements. The owner has now approved the R1–R3
semantic direction and the R9 compatibility requirement, with R4–R8 explicitly
deferred. The [first-slice contract](docs/design/alpha3/LOCAL_BORROW_CONTRACT.md)
records the final case matrix and the R9-reviewed conditional HIR/MIR/v4/v5
encoding. PR #140 was manually merged as `a3b47e6add6abed22eaab845ef21c38be667fee3`.
RM0.1–RM0.3 are closed. RM1 is the separate implementation milestone for this
contract; the concurrency runtime questions do not block it.

- [x] **RM0.0 — Establish ledger and baseline**: close SH6 status, preserve the
  proposal as a non-normative input, list compatibility invariants and decisions.
- [x] **RM0.1 — Choose first semantic slice**: choose the smallest coherent
  relationship extension, settle R1–R3 for that slice, and explicitly defer or
  constrain R4–R8. Design review is required before freeze.
- [x] **RM0.2 — Freeze representation and evidence**: settle R9, normative
  examples, diagnostics, cleanup traces, versioning, and later gate contract.
- [x] **RM0.3 — Review and close**: reconcile the proposal with the normative
  contract, resolve contradictions, and merge the design-only milestone. Start
  feature implementation only under a separate bounded plan after this closure.

## Exit criteria

RM0 closes when all matrix rows have a reviewed resolution or a precise
deferral; the chosen first slice has a normative semantic specification and
testable acceptance/rejection contract; Alpha.2 compatibility is explicit; and
the design-only PR has been manually reviewed and merged. No release tag or
feature implementation is implied by this ledger.

## RM1 implementation checkpoint

PR #141 merged at `bb6bd152e255d081edcd39f87a04f3b371acf016` before RM1
completion. It is a **parser-foundation checkpoint only**: the preferred local
borrow declaration parses with an origin binding and span, while the checker
rejects every such declaration with `M5400`. The merged code does not implement
stored-borrow semantics, HIR/MIR v2, or native v5. Focused parser and Alpha.2
borrowed-return tests passed (41 tests); the canonical fast gate passed
(93 tests) on the merge commit. The [RM1 continuation ledger](RM1_IMPLEMENTATION.md)
tracks the remaining capability and semantic-coherence evidence. Neither PR
#141 nor this checkpoint closes RM1.
