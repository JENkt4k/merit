# Merit development and validation gates

Merit uses one Python orchestration path on Windows, Linux, WSL, GitHub Actions,
and agent environments. Shell and PowerShell scripts are convenience wrappers;
they must not contain a second implementation of the test policy.

## Environment setup

Install Merit and development dependencies into a Python 3.11+ virtual
environment:

```text
python -m pip install --no-build-isolation -e ".[dev]"
```

Validate the core toolchain:

```text
python scripts/doctor.py
```

For the complete release/CI toolchain, including Java and .NET benchmark/parity
runtimes:

```text
python scripts/doctor.py --full
```

On native Windows, `scripts/activate-windows-dev.ps1` configures the repository
virtual environment plus MSYS2 UCRT64 GCC. It does not require WSL.

## Canonical gates

All platforms use the same entry point:

```text
python scripts/gate.py smoke
python scripts/gate.py fast
python scripts/gate.py subsystem
python scripts/gate.py acceptance
python scripts/gate.py full
```

The gates have distinct purposes:

| Gate | Purpose | Expected use |
| --- | --- | --- |
| `smoke` | Small compiler/core sanity check | environment and very early edits |
| `fast` | Curated cross-platform development regression | normal local/agent iteration |
| `subsystem` | Bootstrap and project integration suites | coherent compiler/runtime changes |
| `acceptance` | Ten interpreter/native acceptance projects | acceptance-only verification |
| `full` | Entire pytest suite plus all acceptance projects | PR readiness / merge authority |

A feature change should still run its directly affected pytest file or test names.
The `fast` gate is deliberately not a substitute for feature-specific evidence.

Use `--fail-fast` when diagnosing the first meaningful failure:

```text
python scripts/gate.py subsystem --fail-fast
```

Measure slow tests without changing coverage:

```text
python scripts/gate.py full --durations 50
```

The canonical `subsystem` and `full` gates use two pytest workers with
file-based distribution. Every test is still collected and executed; grouping
by file keeps module/session fixtures and each test module's local isolation
boundary intact while independent native probe builds run concurrently. Direct
focused pytest commands remain serial unless the developer explicitly selects
parallel execution.

Each gate writes a machine-readable terminal result to:

```text
.merit/gates/<gate>/result.json
```

It also prints `MERIT_GATE_RESULT=PASS` or `MERIT_GATE_RESULT=FAIL`. This is
intended for humans, Codex, Jan, and other automation so they do not have to
infer terminal state from long pytest logs.

## Native Windows

From PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e ".[dev]"
.\scripts\activate-windows-dev.ps1
.\scripts\test-windows.ps1 -Gate fast
.\scripts\test-windows.ps1 -Gate full -Durations 50
```

The Windows gate is intended to expose platform-specific behavior including
path separators, drive letters, command quoting, executable suffixes, temporary
directory behavior, file locking, and process execution.

`scripts/ci.ps1` is the non-interactive Windows CI wrapper. `scripts/ci.sh` is
the equivalent Linux/WSL wrapper.

## Agent policy for long-running tests

Agents should use focused tests and `fast` directly. They must not spend model
quota repeatedly polling long-running validation processes.

If a validation command is expected to take more than two minutes, an agent
should either run it once and wait only when the execution environment can
return the terminal result without repeated model turns, or provide the exact
command and stop for human execution. Agents must not emit repeated status
turns such as "still running" or "still green" while waiting.

The normal agent sequence is:

1. directly affected tests;
2. `python scripts/gate.py fast`;
3. affected subsystem tests when appropriate;
4. hand the human the full-gate command when the candidate PR is complete;
5. consume the reported terminal result and perform the final diff/scope audit.

A full gate that passed against an unchanged working tree must not be rerun just
because control returned to an agent. If the tree changes after that gate, the
full gate is stale and must be rerun.

## GitHub Actions

The Local Gate workflow runs the same canonical full gate on Ubuntu and native
Windows. Platform-specific workflow steps provision dependencies only; they do
not implement separate semantic test policies.

The objective is one validation contract across local humans, WSL, native
Windows, GitHub-hosted runners, remote Codex, and local Jan agents.
