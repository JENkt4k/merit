# Minimal Gate Scope Checklist

Use this checklist before expanding `.github/workflows/local-gate.yml`.

An expansion is justified only when all answers are yes:

1. Does it answer a concrete reproducibility, portability, or release question?
2. Can the same check be reproduced locally?
3. Does it avoid duplicating the test and acceptance-project list?
4. Is the added latency proportionate to the defect class it detects?
5. Is the non-Python compiler mature enough for the check to remain stable?
6. Are AST, HIR, and MIR contracts sufficiently stable for the matrix to provide durable evidence?
7. Is the result actionable rather than merely informational?

The original Python-hosted bootstrap phase has ended. Alpha.2 adds only the
Ubuntu/native-Windows jobs required to prove corpus convergence, replacement
acceptance, stage reproducibility, and full-gate portability. Broader matrices,
sanitizers, hosted fuzzing, benchmarks, and release automation still require a
specific actionable justification under this checklist.
