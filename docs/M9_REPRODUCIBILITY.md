# Alpha.2 M9 compiler-stage reproducibility

## Stage identities

- **Stage 0** is the native replacement frontend produced by the independent
  Python reference compiler. It is the bootstrap seed, not the trusted result.
- **Stage 1** is the same Merit compiler project compiled by stage 0 through
  the production replacement pipeline.
- **Stage 2** is the same compiler project compiled by stage 1 through that
  pipeline again.

Each replacement stage uses a fresh isolated copy of the compiler sources.
Existing `.merit`, build, bytecode, and cache artifacts are excluded from the
copy, so a prior repository build cannot satisfy the stage gate.

## Canonical comparison rule

The following artifacts are contractual and must be byte-identical between
stage 1 and stage 2:

- canonical generated C;
- the generated public C header;
- compiler protocol output for an unchanged fixed Merit source probe.

The stage-0, stage-1, and stage-2 drivers must all execute successfully and
produce identical protocol output for that probe.

Native libraries and executable files must execute successfully but are not
required to be byte-identical. Their object metadata, paths, timestamps, and
linker representation are controlled partly by the selected host toolchain and
are not canonical Merit compiler artifacts.

## Evidence

Run:

```text
python scripts/gate.py reproducibility
```

The gate writes `.merit/gates/reproducibility/result.json`, including canonical
SHA-256 values, comparison classifications, platform information, and elapsed
time. Alpha.2 trust requires this gate in clean Ubuntu and native-Windows
checkouts as well as the existing semantic, corpus, acceptance, and full gates.

This gate qualifies the replacement compiler for Alpha.2. It does not claim
later self-hosting policy beyond the stage-1/stage-2 equivalence defined here.
