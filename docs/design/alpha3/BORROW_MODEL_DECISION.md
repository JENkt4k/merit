# RM0 borrowing decision brief

**Recommendation for review, not an approved language contract.** No compiler
or test implementation has changed. See the [comparison](BORROW_MODEL_COMPARISON.md),
[30 cases](BORROW_MODEL_CASES.md), [risks](BORROW_MODEL_RISKS.md), and
[evidence ledger](BORROW_MODEL_EVIDENCE.md).

## Decision requested

Choose the semantic foundation and the minimum portable acceptance contract
for the first Alpha.3 stored-borrow slice. Do not approve syntax or coding from
this brief alone.

**Recommended foundation:** F's explicit separation of resource validity,
read/write permission, and transfer/destruction authority, while preserving
Alpha.2's read-sharing/exclusive-write conflict rule. **Recommended proof
strategy:** A's inferred use-based spans where proven sound. They should be
combined, not maintained as rival language models: the 30 provisional cases
show no A/F acceptance difference under the same policy. [E09–E10]

**Smallest useful slice:** one function-local, immutable stored borrow of an
addressable owner or borrowed parameter, usable for reads and compatible calls;
no aggregate storage, escape, mutable local borrow, or new ABI. Freeze its
origin, validity, move/drop conflict, scope and diagnostic contract before
implementation. Mutable local borrows are a separate next slice unless the
same proof architecture makes them independently verifiable. [E01–E04, E12]

## Alternatives and counterarguments

- **A alone:** viable implementation description, but its phrase "loan span"
  can obscure the separate question of who owns and destroys the referent.
  F provides clearer semantic vocabulary without requiring extra runtime state
  under this policy. [E09]
- **B as permanent language policy:** simpler initial checking and a sound
  conservative option, but cases 04, 07, 09, 13 show safe post-last-use owner
  operations it would reject. B is attractive as an implementation fallback
  only if the required portable acceptance set permits that rejection. [E10, E14]
- **F with novel alias policy:** could eventually support interior mutation,
  runtime-checked aliases, or shared resources, but those are new semantic
  choices with costs and proof obligations, not implied by F. [E15]

The strongest challenge to the recommendation is implementation cost: the
inspected reference checker handles same-call loans and the Python MIR ownership
pass rejects cycles; neither supplies a ready loop-aware local-loan solver.
We have no measured comparative cost. A lexical first checker might deliver
useful safe locals sooner. [E03, E05, E13]

## Reversibility and required evidence

Keep syntax, ABI, protocol, and the exact acceptance set open for review.
Internal inference algorithms can change; public accepted programs, diagnostics,
cleanup, and serialization compatibility become commitments. A conservative
checker is safe but cannot claim conformance to an acceptance rule it rejects.
Before freezing, decide the minimum programs guaranteed to compile and whether
future acceptance expansions require versioning. [E06, E10, E14]

The focused existing borrow baseline passed **36/36** in 10.15s after the
normal MSYS2 PATH and D: temp setup. Two unconfigured attempts failed in native
compilation; those were environment setup failures, not semantic regressions.
This baseline does not exercise any hypothetical stored-borrow syntax. [E08]

## Questions for human approval

1. Should F's separated authority be RM0's semantic vocabulary while retaining
   the current read-sharing/exclusive-write rule?
2. Should the first slice be **immutable function-local stored borrows only**,
   with mutable locals, aggregates, and escaping borrows deferred?
3. Must a conforming first checker accept safe post-last-use owner operations
   (A), or may it initially use lexical rejection (B) as an explicit checker
   limit? What is the minimum portable acceptance set?
4. Should new reference syntax and type identity be decided in this RM0 freeze
   or in a separate syntax review after semantic examples are accepted?

Approval of these questions would guide a later normative spec. It would not
authorize compiler implementation, merge this investigation, or mark RM0
closed. No feature work begins without a separate bounded plan and approval.
