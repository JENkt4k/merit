# Codex Working Agreement — Merit

## Mission

Continue Merit as a deterministic systems language. Preserve exact numerics,
explicit allocation, ownership, contracts, capability-gated hazardous operations,
stable C interoperability, and interpreter/native semantic equivalence.

The active release objective is `v0.1.0-alpha.2`: eliminate Python semantic
authority from normal production compilation while retaining the Python compiler
as an independent oracle until the replacement compiler qualifies as trusted.

Do not broaden the language during alpha.2 closure.

## Start here

1. Read `ALPHA2_CLOSURE.md` first. Treat its open coverage cells and milestone
   ordering as the authoritative alpha.2 work queue.
2. Read `STATUS.md`, `ROADMAP.md`, `BOOTSTRAP_STATUS.md`, and `CODEX_HANDOFF.md`
   for architecture/history. When those conflict with `ALPHA2_CLOSURE.md` or
   current `main`, current `main` and `ALPHA2_CLOSURE.md` win.
3. Read `ARCHITECTURE.md`, `EPOCH-III.md`, and relevant files under `spec/`.
4. Read `docs/DEVELOPMENT_GATES.md` before running broad validation.
5. Re-anchor on current `main`:
   - verify the previous PR is actually merged;
   - verify its authoritative Local Gate;
   - inspect open PRs/branches for overlapping work;
   - never continue from an obsolete branch merely because it exists.
6. Run focused baseline tests for the subsystem being changed before modifying it.

## Non-negotiable invariants

- Every accepted program must have matching interpreter and native C behavior
  for the surface under comparison.
- Side-effecting expressions must be evaluated exactly once in generated C.
- Owned values cannot be copied implicitly.
- Moves, explicit drops, implicit drops, and early returns must never
  double-destroy resources.
- Allocation and other hazardous operations require the appropriate capability.
- Decimal arithmetic remains exact and its rounding policy explicit.
- Stable-layout declarations must preserve deterministic layout and generated
  C assertions.
- Preserve one semantic pipeline; do not create a second independent meaning
  for Merit programs.
- Replacement work must fail closed when a construct is not represented
  faithfully.
- Never silently fall back to Python in replacement mode.
- Python may remain an independent oracle and temporary orchestration layer,
  but must not regain production semantic authority.
- Do not weaken or delete a valid test merely to make a gate green.
- Prefer the final alpha.2 representation over temporary compatibility seams
  when the final representation can reasonably be implemented in the same PR.

## Semantic numeric identifiers

Do not introduce new unexplained numeric literals for semantic compiler
identifiers, tags, opcodes, kinds, statuses, encoded domain values, or similar
meanings. This includes MIR kinds, statement kinds, token kinds, policy IDs,
capability/effect kinds, serialized discriminants, and equivalent domain
identifiers.

Follow `docs/design/NUMERIC_IDENTIFIERS.md` for normative guidance on
classification, canonical placement, representation-boundary exceptions,
bootstrap/Python parity, and discriminants, errors, sentinels, character
encodings, and ordinary mathematical literals.

Use an existing named constant or enum member when one is available. If a new
semantic value is required, define a clearly named symbolic constant or enum
member at the appropriate canonical definition site and reference that symbol
from implementation logic. Explicit numeric values may remain at canonical
serialization, ABI, bootstrap, wire-format, compatibility, or encoding
definition boundaries when the numeric value itself is part of the contract;
consumers should use the symbolic representation rather than duplicate the raw
value.

This rule is forward-looking and does not authorize unrelated cleanup or
refactoring of existing numeric debt.

## Alpha.2 development strategy

The replacement compiler architecture is established through:

```text
Merit source
  -> Merit-native frontend
  -> typed/resolved semantics
  -> ownership/contracts/capabilities/control flow
  -> resolved multi-function bundle
  -> prepared replacement artifacts
  -> canonical replacement MIR
  -> deterministic C
  -> native executable
```

Do not split every internal seam into a separate PR anymore.

Prefer the largest coherent vertical milestone that can be completely validated.
A PR may touch many files and contain substantial implementation work if it
closes one coherent semantic block and the full gate remains authoritative.

Current large milestone sequence:

1. accepted-alpha statement/control-flow closure;
2. resource model and payload-enum lifecycle closure;
3. exact numeric and aggregate closure;
4. generics/traits closure;
5. module/project/import/export closure;
6. complete accepted/rejected corpus convergence;
7. all alpha acceptance applications through replacement compilation;
8. production compiler-path cutover;
9. stage-0/stage-1 reproducibility and deterministic equivalence;
10. alpha.2 release audit/documentation closure.

Update `ALPHA2_CLOSURE.md` as evidence changes. Do not mark a surface closed
because a parser fixture exists; closure requires the vertical replacement path
defined in that document.

## Development loop

1. Re-anchor on `main` and verify the previous merge/gate.
2. Read `ALPHA2_CLOSURE.md`.
3. Choose the highest-value coherent open milestone.
4. Create one branch. Do not start parallel autonomous branches.
5. Analyze the complete affected surface before editing.
6. Implement the complete vertical slice, including as applicable:
   - accepted cases;
   - rejected/fail-closed cases;
   - Python-oracle differential cases;
   - interpreter/native parity;
   - replacement-driver coverage;
   - deterministic artifact checks;
   - acceptance-project coverage.
7. Run focused tests during implementation.
8. Run affected subsystem tests after coherent changes.
9. Run the full clean gate only when the candidate PR is believed complete,
   or when a failure may be cross-cutting.
10. Open or repair exactly one PR.
11. Treat the canonical GitHub full gates as authoritative.
12. Diagnose the first/root failure before making changes. Do not react to the
    raw fan-out failure count as if each failed test were independent.
13. Repair failures on that same PR until green.
14. Stop for manual merge review. Never auto-merge.
15. Do not begin the next milestone until the previous PR is confirmed on main.

## Testing policy

Use the narrowest test level that answers the current question. The canonical
cross-platform orchestration is `scripts/gate.py`; shell and PowerShell scripts
are wrappers only.

### During implementation

Run the directly affected test file or explicit pytest test names.

Examples:

```bash
python -m pytest tests/project/test_relevant_gate.py -q
python -m pytest tests/project/test_relevant_gate.py::test_specific_case -q
python scripts/gate.py fast
```

### After a coherent subsystem change

Run the affected subsystem/project tests, then use the canonical subsystem gate
when broad bootstrap/project evidence is appropriate:

```bash
python scripts/gate.py subsystem
```

### Before PR readiness

Run the complete gate from the platform being validated:

```bash
python scripts/doctor.py --full
python scripts/gate.py full --durations 50
```

Linux/WSL convenience wrapper:

```bash
bash scripts/ci.sh --durations 50
```

Native Windows convenience wrapper:

```powershell
.\scripts\test-windows.ps1 -Gate full -Durations 50
```

The GitHub Ubuntu and native Windows full gates are clean-environment authorities.
Do not repeatedly run the entire suite after every small source edit.

### Long-running validation and model quota

Do not poll long-running tests with repeated model turns. If a command is
expected to take more than two minutes, either run it in an execution environment
that can return the terminal result without repeated model polling, or give the
human the exact command and stop for manual execution. Do not emit repeated
"still running" or "still green" turns.

A previously reported full-gate pass remains valid only while the working tree is
unchanged. Do not rerun a full gate merely because control returned to the agent;
if the tree changed after the gate, rerun it before claiming PR readiness.

Each canonical gate writes `.merit/gates/<gate>/result.json` and prints a terminal
`MERIT_GATE_RESULT=PASS` or `MERIT_GATE_RESULT=FAIL` marker for humans and agents.

If a full run fails:

1. find the earliest meaningful/root failure;
2. determine whether later failures are fan-out;
3. fix the root cause;
4. rerun focused tests first;
5. rerun the full gate only after the focused repair passes.

## Development environment

Supported development environments include:

- native Windows with Python 3.11+, MSYS2 UCRT64 GCC, Java, and .NET;
- WSL2/Linux with Python 3.11+, GCC/Clang, Java, and .NET;
- GitHub-hosted Windows and Ubuntu runners using the same canonical Python gate.

Native Windows is a first-class validation environment, not merely a smoke target.
Run `python scripts/doctor.py` for the core development toolchain and
`python scripts/doctor.py --full` for the complete full-gate toolchain.

On Windows, `scripts/activate-windows-dev.ps1` configures the virtual environment,
MSYS2 UCRT64 GCC, and stable temporary paths. On Linux/WSL, no Bash-specific test
policy should exist beyond thin wrappers around the Python gate.

Repository placement on the native Linux filesystem is still preferred for WSL
performance, but Windows checkouts must remain fully supported because remote
Codex and local Jan/agent workflows may run outside WSL.

## Commands

Cross-platform canonical commands:

```text
python scripts/doctor.py
python scripts/gate.py smoke
python scripts/gate.py fast
python scripts/gate.py subsystem
python scripts/gate.py acceptance
python scripts/gate.py full --durations 50
```

Convenience wrappers:

```bash
./scripts/bootstrap.sh
./scripts/test.sh
bash scripts/ci.sh
```

```powershell
.\scripts\activate-windows-dev.ps1
.\scripts\test-windows.ps1 -Gate fast
.\scripts\test-windows.ps1 -Gate full
.\scripts\ci.ps1 -Gate full
```

Use focused pytest invocations during implementation rather than automatically
running the full gate after each edit.

## Current checkpoint

`v0.1.0-alpha.1` is complete.

Development is closing `v0.1.0-alpha.2`.

The following production replacement boundaries are already established:

- Merit-native source lexing/discovery;
- source-backed functions;
- multi-function discovery and slicing;
- ownership/control/contracts/capabilities;
- native capability declaration catalogs;
- native payload-free enum catalogs;
- typed match-subject enum identity;
- per-match enum identity for multiple matches/enums;
- resolved multi-function MRBF bundles;
- prepared replacement artifacts;
- canonical replacement MIR reconstruction;
- deterministic C generation;
- native execution;
- fail-closed replacement project builds.

Do not recreate these milestones or introduce older transitional architecture
because older status documents mention them.

The active objective is to close the remaining alpha.1 semantic surface through
this already-established replacement pipeline, as tracked in
`ALPHA2_CLOSURE.md`.

Keep reference, replacement/bootstrap, trusted, and self-hosted stages distinct.
Self-hosting begins only after the alpha.2 replacement compiler satisfies the
trust/reproducibility gate.
