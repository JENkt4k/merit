# Alpha.2 M6 closure notes

M6 closes complete Alpha.1 accepted/rejected corpus convergence without broadening the language.

Authoritative evidence:

- historical Python reference authority: every `tests/test_epoch_*.py` module;
- canonical same-source manifest: `tests/project/alpha1_corpus_v1.json`;
- reference/replacement/native convergence: `tests/bootstrap/test_alpha1_corpus_convergence.py`;
- executable report: `scripts/alpha1_corpus_report.py` via `python scripts/gate.py corpus`;
- hosted dedicated corpus job plus ordinary Linux and native-Windows full gates.

The manifest's required-surface set is mechanically checked against the union of accepted and rejected case coverage. Accepted cases require reference checking, reference native execution, deterministic replacement preparation, replacement native execution, and exact process-output parity. Rejected cases require both semantic paths to reject deterministically; replacement preparation must not publish a manifest after a native-front-end rejection.

M7 remains responsible for migrating the complete acceptance-application set to replacement mode. M8 remains responsible for changing the default production compiler path.
