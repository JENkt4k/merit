# M6 corpus gate

The dedicated Alpha.2 M6 gate is:

```text
python scripts/gate.py corpus
```

It runs the complete historical Alpha.1 `tests/test_epoch_*.py` reference authority and the canonical same-source reference/replacement convergence suite. Its generated report is `.merit/gates/corpus/coverage.json`.

This gate complements, rather than replaces, the normal smoke, fast, subsystem, acceptance, and full gates. The hosted pull-request workflow runs M6 directly on Ubuntu while the ordinary Linux and native-Windows full gates execute the convergence tests through the normal test tree.
