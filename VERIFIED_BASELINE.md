# Verified Baseline

Verification completed on 2026-09-12 for merged PR #115 commit
`12ad01eb6e33b2e1d49f79b634261c5e75d412a6`.

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
local stage reproducibility: PASS in 838.457 seconds
Ubuntu stage reproducibility: PASS in approximately 15 minutes
native-Windows stage reproducibility: PASS in approximately 18 minutes
local full gate: 1149 passed, 1 skipped; 10/10 reference acceptance; PASS
Ubuntu full gate: PASS
native-Windows full gate: PASS
```

The reproducibility gate constructs the reference-produced native stage 0,
uses it to construct stage 1, and uses stage 1 to construct stage 2 from fresh
isolated compiler sources. Stage 1 and stage 2 produce byte-identical canonical
C and public headers, and all three drivers produce identical fixed-probe
protocol output. Platform-native library and executable bytes are execution
evidence rather than canonical comparison inputs.

This baseline proves M1-M9 on the merged tree. The M10 release candidate must
still pass its own clean reproducibility and full gates after documentation and
version metadata are finalized; its hosted checks and manual tag remain the
final Alpha.2 release authority.
