# Alpha.1 corpus convergence

Alpha.2 M6 proves that the documented Alpha.1 semantic surface converges between the independent Python reference compiler and the Merit-native replacement compiler.

The canonical same-source corpus is `tests/project/alpha1_corpus_v1.json`. It contains accepted and rejected programs and declares the semantic surfaces each case covers. `tests/bootstrap/test_alpha1_corpus_convergence.py` enforces that every required surface is represented.

For accepted cases the test performs all of the following on the same source project:

1. load and check with the Python reference compiler;
2. build and execute the reference native artifact;
3. prepare replacement artifacts through the concrete Merit-native frontend driver;
4. prepare the replacement artifacts a second time and require byte-identical manifests, snapshots, and canonical project-source artifacts;
5. build and execute the replacement native artifact;
6. require identical exit status, stdout, and stderr between reference and replacement native execution.

For rejected cases the test independently runs the reference and replacement boundaries twice. Both must reject, each boundary must produce a stable stage/type/message tuple, and cases that reach replacement preparation must fail before a replacement manifest is published. Project-loader failures are shared project semantics and are recorded as that earlier boundary rather than being misclassified as replacement semantic acceptance.

The historical Alpha.1 reference authority remains the complete `tests/test_epoch_*.py` set. M6 does not replace or rewrite those tests. `scripts/alpha1_corpus_report.py` runs the full historical reference corpus and then the same-source convergence suite, producing `.merit/gates/corpus/coverage.json`.

Run the dedicated gate with:

```text
python scripts/gate.py corpus
```

The pull-request workflow also runs this gate on Ubuntu and uploads the generated JSON report as `alpha1-corpus-coverage`. The ordinary Linux and native-Windows full gates still execute the convergence test because it lives inside the normal `tests` tree.

M6 is closed only when the dedicated corpus gate and the ordinary hosted full gates are green. Acceptance-application migration is intentionally M7 and is not part of this corpus contract.
