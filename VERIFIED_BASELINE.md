# Verified Baseline

Release verification completed on 2026-09-12 for merged PR #116 commit
`53699f28f0877483081aed81f6b3488d0cf6ffd5`, tagged
`v0.1.0-alpha.2`.

Canonical commands:

```bash
python scripts/gate.py corpus
python scripts/gate.py acceptance-replacement
python scripts/gate.py reproducibility
python scripts/gate.py full --durations 50
```

Results:

```text
Alpha.1 accepted/rejected corpus convergence: PASS
replacement acceptance: 10/10 projects, PASS
local stage reproducibility: PASS in 833.5 seconds
Ubuntu stage reproducibility: PASS
native-Windows stage reproducibility: PASS
local full gate: 1150 passed, 1 skipped; 10/10 reference and replacement acceptance; PASS in 2122.843 seconds
Ubuntu full gate: PASS
native-Windows full gate: PASS
```

The reproducibility gate constructs the reference-produced native stage 0,
uses it to construct stage 1, and uses stage 1 to construct stage 2 from fresh
isolated compiler sources. Stage 1 and stage 2 produce byte-identical canonical
C and public headers, and all three drivers produce identical fixed-probe
protocol output. Platform-native library and executable bytes are execution
evidence rather than canonical comparison inputs.

This baseline proves M1-M10 on the tagged tree. PR #116 passed clean local and
hosted reproducibility/full gates before manual merge and tagging. Current
technical-debt work begins from this immutable compatibility baseline and is
tracked in `POST_ALPHA2_CLEANUP.md`.
