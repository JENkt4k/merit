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

During the Python-hosted bootstrap phase, the expected answer for broad matrices, sanitizers, hosted fuzzing, benchmarks, and release automation is normally no.
