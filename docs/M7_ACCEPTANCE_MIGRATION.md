# Alpha.2 M7 acceptance migration

## Objective

M7 proves that every canonical Alpha.1 acceptance application compiles and runs through the production replacement compiler with no Python semantic lowering or silent reference fallback.

M6 established same-source semantic corpus convergence. M7 raises the evidence boundary from isolated corpus programs to the repository's real multi-feature applications.

## Canonical acceptance set

`scripts/gate.py` currently verifies ten projects:

1. `text_pipeline`
2. `binary_packet`
3. `generic_result`
4. `trait_bounds`
5. `generic_collections`
6. `borrowed_views`
7. `bootstrap_lexer`
8. `cobol_finance_modernization`
9. `filesystem_capabilities`
10. `ledger_app`

The exact-decimal `ledger_app` is mandatory M7 evidence.

## Required replacement path

Each project must traverse the real project boundary:

```text
project sources
  -> deterministic project loading
  -> concrete Merit-native replacement frontend
  -> prepared replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
  -> observable application result
```

The M7 harness must not call Python semantic lowering to make a replacement build succeed. Unsupported replacement behavior must fail closed.

## Implementation plan

### 1. Audit the ten applications

For each project record:

- source units and entry module;
- language surfaces exercised;
- capabilities and filesystem inputs/outputs;
- expected exit status, stdout/stderr, and observable files;
- whether shared-library/header output is part of the application's acceptance contract;
- current reference verification path;
- first replacement boundary that fails, if any.

The audit is evidence and triage. It must not weaken an application merely to make replacement mode pass.

### 2. Add an explicit replacement acceptance harness

Extend the canonical gate with an M7-specific acceptance path that, for each project:

1. verifies/builds the established reference application;
2. prepares replacement artifacts through the concrete native frontend;
3. builds the application with `--compiler replacement`;
4. executes the replacement artifact;
5. compares the application's observable behavior with the established reference acceptance contract;
6. records deterministic machine-readable per-project results.

Filesystem-dependent projects must run in isolated temporary workspaces, as the existing acceptance gate already does.

### 3. Prove no fallback

Replacement acceptance must use the production replacement compiler boundary and must fail if preparation/build/run attempts to use reference semantic lowering. Existing replacement-mode fail-closed behavior is the required policy; M7 must exercise it at application scale.

### 4. Prove determinism

For each project, prepare/build the replacement inputs twice from unchanged source and compare the canonical replacement artifacts that are defined as deterministic. At minimum this includes prepared manifests/project-source artifacts and canonical generated source where the current replacement contract exposes them.

Do not require byte identity for platform/toolchain outputs that are not defined as reproducible; stage/release reproducibility belongs to M9.

### 5. Preserve application-level behavior

M7 is not satisfied by compilation alone. Compare the observable contract appropriate to each application:

- process exit status;
- stdout/stderr where meaningful;
- generated files and file contents where meaningful;
- foreign/shared-library behavior where already part of the acceptance project.

### 6. Classify failures narrowly

A failing application is classified as one of:

- an already-documented Alpha.1 semantic surface missing from replacement composition;
- project/module/export plumbing defect;
- application harness/environment defect;
- out-of-scope feature accidentally required by the application.

Fix genuine Alpha.1 replacement gaps. Do not broaden Alpha.1 or introduce a compatibility fallback to close M7.

### 7. Canonical gate and CI

Add a dedicated gate, preferably:

```text
python scripts/gate.py acceptance-replacement
```

The ordinary `acceptance` gate remains the independent established acceptance/reference contract. `full` must include replacement acceptance before M7 is declared closed.

Run M7 on Ubuntu and native Windows. Keep exact test/project counts in generated gate evidence rather than freezing transient counts in status prose.

## Closure criteria

M7 is CLOSED only when all of the following are true:

- all 10 canonical acceptance projects pass through replacement mode;
- `ledger_app` passes through replacement mode with its exact-decimal behavior intact;
- replacement execution agrees with each application's established observable acceptance contract;
- no Python semantic lowering or silent fallback is used by replacement builds;
- deterministic replacement artifacts agree on repeated unchanged builds where the artifact contract requires determinism;
- filesystem/capability applications pass in isolated workspaces;
- project/module/import/visibility/generic/trait/ownership composition remains intact;
- dedicated M7 gate is green;
- canonical Ubuntu full gate is green;
- canonical native-Windows full gate is green;
- `ALPHA2_CLOSURE.md` records concrete M7 evidence before the milestone is marked CLOSED.

## Explicit non-goals

M7 does not:

- make replacement compilation the default compiler path (M8);
- remove Python as the independent oracle (M8/M9 trust work);
- establish stage-0/stage-1 equivalence or release reproducibility (M9);
- broaden the Alpha.1 language surface;
- redesign acceptance applications merely to avoid replacement defects;
- perform the final Alpha.2 release/documentation audit (M10).

## Expected implementation order

```text
acceptance inventory
  -> replacement acceptance harness
  -> first 10-project run
  -> failure classification
  -> repair genuine Alpha.1 composition gaps
  -> deterministic artifact evidence
  -> Ubuntu + Windows integration
  -> update ALPHA2_CLOSURE.md with measured evidence
  -> M7 closure
```

M7 should remain one coherent milestone PR. Internal commits may be split by harness, project-gap repairs, determinism/CI, and closure documentation.