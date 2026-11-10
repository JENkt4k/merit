# Borrow-model investigation: evidence ledger

Status: design investigation on `main` merge `93a2c3c` (PR #136). `VERIFIED`
means inspected implementation or an explicitly named executed test; source
inspection alone does not prove whole-pipeline behavior. `DERIVED` means a
consequence of stated provisional semantics. `HYPOTHETICAL` means a proposed
feature or mechanism. `UNRESOLVED` identifies missing evidence. No row freezes
the language.

| ID | Class | Claim and evidence | Assumption or limit |
| --- | --- | --- | --- |
| E01 | VERIFIED (source) | `spec/OWNERSHIP.md`, Borrowed returns and Deliberate limits: current returned borrows are ephemeral, parameter-origin checked, and cannot be stored in locals/aggregates. | Documented contract; independently sampled in E08. |
| E02 | VERIFIED (source) | `merit/compiler.py:914` `OwnershipEffects` tracks owned roots, consumption sites, explicit drops; `Checker.block` at ~1222 checks statement state. | Reference path; not evidence of general stored-loan tracking. |
| E03 | VERIFIED (source) | `merit/compiler.py:1108` `check_borrowed_return` and ~1145 `borrowed_return_origin` require an origin in borrowed parameters; ~1477 call checking collects same-call loans and rejects conflicts. | Call-level loan lists are not inferred local loan spans. |
| E04 | VERIFIED (source) | `merit/compiler.py:697` `VarState`; ~1698 interpreter `block`, ~1793 `eval`; ~1981 and ~2240+ C emitter use pointer modes for borrowed parameters/results. | Physical C pointer representation is an implementation choice. |
| E05 | VERIFIED (source) | `merit/bootstrap/mir_contract.py:111` `MirInstruction` includes ownership mode; ~232 `MirFunction` records borrowed origin. `mir_ownership.py:19` has transfer modes and ~120 topological block pass rejects cycles. | This older Python MIR ownership pass is not a general loop-aware loan solver; production Merit stage has additional paths. |
| E06 | VERIFIED (source) | `SELF_HOSTING.md`, SH3 resource-effect audit: current lifecycle catalogs encode exclusive Alpha.2 facts; new relationships require a versioned schema, not reinterpretation. | Architecture constraint, not design approval. |
| E07 | VERIFIED (source) | `tests/test_alpha3.py` and `tests/test_ordered_expression_lowering.py` include conflicting mutable/shared call loans; `tests/test_epoch_iii_borrowed_returns.py` covers return origins, relay, and rejection of storage; `tests/test_ephemeral_borrow_boundary.py` lists prohibited uses. | These are identified tests; executed verification is recorded separately below. |
| E08 | VERIFIED (test) | Focused pytest on 2026-11-09 passed 36/36 in 10.15s after setting MSYS2 UCRT64 `bin` on PATH, `CC` to its GCC, and TEMP/TMP to D:. Earlier unconfigured runs had 26 pass/10 native failures. | Current Alpha.2 reference/native boundary only; no local-borrow feature is tested. |
| E16 | VERIFIED (source) | `examples/projects/bootstrap_lexer/src/mir_ownership_flow.mrt:8` defines `MirOwnershipBinding` with binding/local IDs and `owned`, `mutable`, `needs_drop` flags; `mir_resolved_source_function_bundle.mrt` consumes these records. | These are current Alpha.2 metadata, not a general resource-validity/access-authority relation. |
| E17 | VERIFIED (external design reference) | [Rust compiler borrow-check guide](https://rustc-dev-guide.rust-lang.org/borrow_check.html) describes MIR-based borrow checking and control-flow-derived regions; [C++ Core Guidelines resource management](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#S-resource) favors explicit resource handles; [Swift ARC guide](https://github.com/swiftlang/swift-book/blob/main/TSPL.docc/LanguageGuide/AutomaticReferenceCounting.md) documents shared-reference accounting and cycles. | Comparative precedents only; none proves a Merit model sound or cheap. |
| E09 | DERIVED | Under definitions A and F in the comparison, an inferred loan span can implement separated validity, access, and destruction authority without new runtime state for local references. | Requires a sound alias/place relation, control-flow liveness, and no untracked escape. |
| E10 | DERIVED | B must reject owner mutation after the borrow's last use but before lexical scope end if it retains an exclusive loan until block exit; A/F may accept only after proving last use on all paths. | No destructor or alias uses of the reference later. |
| E11 | HYPOTHETICAL | Local borrow bindings could carry origin/place, permission, and validity facts in a future typed representation; MIR would need explicit loan effects. | No source or MIR change is made here. |
| E12 | UNRESOLVED | Local-borrow syntax, reborrowing, reassignment, loops, join precision, and diagnostic identity are not specified by current Alpha.2 semantics. | Requires RM0 decision and design examples. |
| E13 | UNRESOLVED | Relative cost of a full non-lexical checker versus a lexical checker on the 46-module compiler is unmeasured. | Needs a later isolated prototype/benchmark, not a guessed estimate. |
| E14 | DERIVED | Conservative rejection can preserve safety but changes acceptance and portability if the language contract promises acceptance of a class the checker cannot prove. | Define a minimum required acceptance set before freezing. |
| E15 | HYPOTHETICAL | Shared/weak, regions, pinning, foreign ownership, tensor views, and concurrency can use separate authority dimensions, but each needs independent lifetime and runtime rules. | Compatibility is not established by naming orthogonal dimensions. |

## Verification log

| Command | Result | Scope |
| --- | --- | --- |
| `rg`/`Get-Content` inspection of sources and named tests above | Completed | Source inspection, not execution. |
| `.venv\Scripts\python.exe -m pytest -q --basetemp=D:\Temp\merit-tests\rm0-borrow-baseline tests/test_ephemeral_borrow_boundary.py tests/test_epoch_iii_borrowed_returns.py` | 26 passed, 10 failed in 3.29s; first native failure `FileNotFoundError` for `cc` | Reference checker tests ran; native parity unavailable. |
| Same command with `CC=C:\msys64\ucrt64\bin\gcc.exe` and distinct D: base temp | 26 passed, 10 failed in 2.78s; first failure `CalledProcessError` from GCC | External C toolchain still failed; no assertion of semantic failure. |
| Same two files with MSYS2 UCRT64 `bin` prepended to PATH, `CC` set to `C:\msys64\ucrt64\bin\gcc.exe`, TEMP/TMP=`D:\Temp\merit-gcc\tmp`, and D: base temp | **36 passed in 10.15s** | Configured native baseline for current borrow tests; no hypothetical syntax tested. |

## Evidence gaps

- Production Merit-native source structures and binary protocol need a
  field-by-field implementation audit before the later R9 freeze. The SH3 seam
  ledger identifies the boundary but does not prove a loan solver exists.
- No conceptual case below is an executable Alpha.3 test. Accepted/rejected
  outcomes are conditional on provisional model definitions.
- Compile-time, runtime, memory, and artifact-size costs of A/B/F have not been
  measured; no numerical ranking is justified.
- The initial native failures were environment setup, resolved by the configured
  MSYS2 PATH and D: temp. Broader Alpha.2/cross-platform evidence was not rerun.
