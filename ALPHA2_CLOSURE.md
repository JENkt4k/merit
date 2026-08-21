# Merit v0.1.0-alpha.2 Closure Matrix

## Objective

`v0.1.0-alpha.2` removes Python semantic authority from normal production compilation for the complete documented alpha.1 language surface.

Python remains the independent reference/oracle until trust qualification.

This file is the authoritative work queue for alpha.2 closure.

A feature is not "closed" because isolated parser/HIR/MIR tests exist. Closure means the supported source construct travels through the production replacement path and satisfies the evidence requirements below.

## Production replacement path

```text
Merit source
  -> concrete Merit-native replacement driver
  -> native source/function/declaration discovery
  -> typed/resolved semantics
  -> ownership/contracts/capabilities/control flow
  -> resolved multi-function MRBF bundle
  -> prepared replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
```

## Closure criteria

A semantic surface is CLOSED when all applicable columns are satisfied:

- **Reference:** Python/reference compiler accepts/rejects correctly.
- **Replacement:** production replacement compiler represents it without fallback.
- **Differential:** replacement agrees with reference for accepted/rejected cases.
- **Native:** generated C compiles and behaves identically.
- **Negative:** invalid cases fail closed with deterministic diagnostics/status.
- **Acceptance:** exercised by an acceptance application where applicable.
- **Determinism:** relevant serialized/generated artifacts are stable.
- **Windows:** covered by Windows native smoke where platform-relevant.

## Current coverage matrix

| Semantic surface | Reference | Replacement | Differential | Native | Negative | Acceptance | State |
|---|---:|---:|---:|---:|---:|---:|---|
| source lexing/tokenization | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| function discovery | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| multiple functions/source | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| basic let/var bindings | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| source ownership metadata | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| basic moves/drops | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| contracts | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| capability declarations | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| capability scopes/effects | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| payload-free enums | ✓ | ✓ | ✓ | ✓ | ✓ | partial | CLOSED |
| multiple enums | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| multiple match statements | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| typed match enum identity | ✓ | ✓ | ✓ | ✓ | ✓ | — | CLOSED |
| multi-function MRBF | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| canonical replacement MIR | ✓ | ✓ | ✓ | ✓ | ✓ | indirect | CLOSED |
| deterministic C emission | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| replacement executable | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | CLOSED |
| payload-bearing enums | ✓ | OPEN | OPEN | OPEN | partial | — | OPEN |
| complete branching/control flow | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| loops | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| rich owned structs/aggregates | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| strings/buffers complete alpha surface | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| exact decimal complete surface | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| bounded integers complete surface | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | partial | OPEN |
| generic functions/types | ✓ | OPEN/PARTIAL | OPEN | OPEN | partial | partial | OPEN |
| generic collections | ✓ | OPEN/PARTIAL | OPEN | OPEN | partial | partial | OPEN |
| coherent traits | ✓ | OPEN/PARTIAL | OPEN | OPEN | partial | partial | OPEN |
| cross-module imports | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| visibility/qualified names | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| stable exports/shared libraries | ✓ | PARTIAL | PARTIAL | PARTIAL | partial | ✓ | OPEN |
| all alpha accepted corpus | ✓ | OPEN | OPEN | OPEN | — | — | OPEN |
| all alpha rejected corpus | ✓ | OPEN | OPEN | — | OPEN | — | OPEN |
| all nine acceptance projects | ✓ | OPEN | OPEN | OPEN | — | OPEN | OPEN |
| replacement default compiler path | — | OPEN | — | OPEN | OPEN | OPEN | OPEN |
| Python semantic authority removed | — | OPEN | — | — | — | — | OPEN |
| stage-0/stage-1 equivalence | — | OPEN | OPEN | OPEN | — | — | OPEN |
| reproducible alpha.2 release | — | OPEN | OPEN | OPEN | — | ✓ | OPEN |

`PARTIAL` is intentionally conservative. Replace it with concrete evidence rather than assuming coverage from neighboring tests.

## Large remaining milestones

### M1 — Accepted-alpha statement/control-flow closure

**Goal:** Drive every remaining alpha.1 statement/expression/control-flow form through the production replacement pipeline.

Includes as applicable:

- conditionals;
- loops;
- returns and early termination;
- nested control flow;
- expression statements;
- assignment/replace;
- match integration;
- path-sensitive ownership across branches.

**Exit criteria:**

- relevant coverage cells CLOSED;
- accepted/rejected differential cases;
- interpreter/native parity;
- no Python fallback;
- full Local Gate green.

### M2 — Resource and payload-enum lifecycle closure

**Goal:** Close owned aggregate/resource semantics including payload-bearing enums.

Includes:

- recursive lifecycle classification;
- enum payload ownership;
- destructors;
- move/drop/replace semantics;
- early-return cleanup;
- no double destruction;
- negative ownership cases.

### M3 — Exact numerics and aggregate closure

**Goal:** Move the complete alpha.1 decimal/bounded/string/buffer/aggregate surface through replacement compilation.

### M4 — Generics and traits closure

**Goal:** Move explicit generics, generic collections, coherent trait resolution and instantiated operations through replacement compilation.

Do not introduce a second generic/trait semantic model.

### M5 — Module/project closure

**Goal:** Close multi-source-unit compilation, imports, qualified names, visibility, exports, stable-layout/shared-library interactions.

### M6 — Corpus convergence

**Goal:** Run the complete alpha.1 accepted and rejected corpus against reference and replacement compilers and eliminate every unexplained discrepancy.

Output should be an executable/generated coverage report where practical.

### M7 — Acceptance migration

**Goal:** All nine alpha acceptance projects compile/run through replacement mode with no Python semantic lowering.

The exact-decimal ledger is mandatory evidence.

### M8 — Production cutover

**Goal:** Make replacement compilation the normal compiler path for the alpha surface.

Python becomes explicitly reference/oracle-only.

No silent fallback.

### M9 — Trust/reproducibility

**Goal:**

- stage-0 produces stage-1;
- repeated stage builds are deterministic;
- canonical artifacts are equivalent under the documented comparison rule;
- clean environment reproduction succeeds.

### M10 — Alpha.2 release closure

**Goal:**

- STATUS/ROADMAP/BOOTSTRAP_STATUS/manual synchronized;
- limitations accurate;
- complete release gate green;
- clean-tree reproducibility confirmed;
- alpha.2 release notes prepared.

## PR sizing policy

Prefer one PR per milestone above where practical.

Split a milestone only when:

1. a genuinely independent architectural prerequisite is discovered;
2. the PR becomes impossible to validate coherently;
3. separate changes have materially different rollback/trust boundaries.

Do **not** split merely because a change touches many files or exceeds an arbitrary line count.

Do **not** add temporary compatibility seams when the final alpha.2 representation can reasonably be implemented and tested in the same PR.

## Testing cadence

During development:

```text
specific failing test
    ↓
focused test file
    ↓
affected subsystem
    ↓
full scripts/ci.sh
```

Do not run the full suite after every small edit.

GitHub Local Gate remains authoritative before merge.

## Failure handling

Large test counts often fan out from one compiler/bootstrap failure.

When the suite fails:

1. inspect the first meaningful failure;
2. determine the shared root cause;
3. fix the root cause rather than individual downstream tests;
4. run focused tests;
5. run the full gate once the root repair passes.

## Completion condition

Alpha.2 is complete when:

1. the documented alpha.1 accepted surface compiles through replacement mode;
2. the documented rejected surface remains rejected;
3. reference/replacement semantic parity is demonstrated;
4. all acceptance applications pass;
5. normal production compilation no longer uses Python semantic lowering;
6. deterministic stage/reproducibility criteria pass;
7. release documentation and limitations match reality.
