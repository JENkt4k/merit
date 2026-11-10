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
| E09 | DERIVED | Under F's authority decomposition, A-style inferred loan spans can prove local access restrictions without new runtime state for local references. | Requires a sound alias/place relation, control-flow liveness, and no untracked escape; F is not a competing solver. |
| E10 | DERIVED | B must reject owner mutation after the borrow's last use but before lexical scope end if it retains a read loan until block exit; an A-style proof may accept after proving final use. | No destructor or alias uses of the reference later. |
| E11 | HYPOTHETICAL | Local borrow bindings could carry origin/place, permission, and validity facts in a future typed representation; MIR would need explicit loan effects. | No source or MIR change is made here. |
| E12 | PARTIALLY RESOLVED | The owner approved the preferred provisional local-borrow spelling and stable diagnostic identities/spans for the first slice. Reborrowing, reassignment, loops, join precision, and wider syntax remain deferred. | Production grammar and compiler behavior are unchanged; see E21–E23. |
| E13 | UNRESOLVED | Relative cost of a full non-lexical checker versus a lexical checker on the 46-module compiler is unmeasured. | Needs a later isolated prototype/benchmark, not a guessed estimate. |
| E14 | DERIVED | Conservative rejection can preserve safety but changes acceptance and portability if the language contract promises acceptance of a class the checker cannot prove. | Define a minimum required acceptance set before freezing. |
| E15 | HYPOTHETICAL | Shared/weak, regions, pinning, foreign ownership, tensor views, and concurrency can use separate authority dimensions, but each needs independent lifetime and runtime rules. | Compatibility is not established by naming orthogonal dimensions. |
| E18 | VERIFIED (human direction) | Owner review of PR #137 approves F as preferred semantic foundation, immutable function-local stored borrows as proposed first slice, A-style inferred spans and post-final-use acceptance as preferred, and defers surface syntax. | Design direction only; no normative freeze, implementation, new ABI, or merge approval. |
| E19 | VERIFIED (human direction) | The owner approved cases 01, 02, 04, 07, 09, 18, 24 as the straight-line minimum under known provenance/no hidden uses/non-retaining effects, with required rejection of 05, 06, 08, 22, 23, 28. | The [contract](LOCAL_BORROW_CONTRACT.md) is awaiting design-only review; no compiler case has executed. |
| E20 | VERIFIED (source audit) | `MirOwnershipBinding` flags do not establish loan origin/identity or final-use effects; `bootstrap-hir-v1`, `bootstrap-mir-v1`, and native v4 artifacts are current encodings. The [implementation plan](LOCAL_BORROW_IMPLEMENTATION_PLAN.md) maps every affected boundary. | Proposed v2/v5 extensions remain unimplemented and need byte-level review. |
| E21 | VERIFIED (human direction) | The owner approved a distinct non-owning immutable local binding mode, compatible with proven non-retaining `borrow T` calls but not owned value parameters, returns, or aggregate storage; F/A semantics and R3 cleanup are approved for the first slice. | No general reference type, generic compatibility, wider syntax, RM0 freeze, or code authorization. |
| E22 | VERIFIED (in-memory grammar probe) | A naive LALR local-borrow declaration parsed `let r: borrow Box = borrow x;` but rejected an existing accepted `struct borrow` / `let x:borrow = ...` program. A contextual-token prototype parsed both, plus existing `borrow` local and parameter forms. Current `Checker(parse(...)).check()` accepts the old type/name programs. | Prototype did not edit production grammar or exercise comments between new tokens; it proves a compatibility hazard and a viable direction, not complete grammar acceptance. |
| E23 | PROPOSED CONTRACT | The [first-slice contract](LOCAL_BORROW_CONTRACT.md) specifies stable diagnostic identities/spans, conditional HIR/MIR v1/v2 and native artifact v4/v5 framing, old-program byte stability, deterministic loan record order, and malformed-record rejection. | Proposed representation needs design-only review/merge before implementation; no artifact has been emitted. |

## Verification log

| Command | Result | Scope |
| --- | --- | --- |
| `rg`/`Get-Content` inspection of sources and named tests above | Completed | Source inspection, not execution. |
| `.venv\Scripts\python.exe -m pytest -q --basetemp=D:\Temp\merit-tests\rm0-borrow-baseline tests/test_ephemeral_borrow_boundary.py tests/test_epoch_iii_borrowed_returns.py` | 26 passed, 10 failed in 3.29s; first native failure `FileNotFoundError` for `cc` | Reference checker tests ran; native parity unavailable. |
| Same command with `CC=C:\msys64\ucrt64\bin\gcc.exe` and distinct D: base temp | 26 passed, 10 failed in 2.78s; first failure `CalledProcessError` from GCC | External C toolchain still failed; no assertion of semantic failure. |
| Same two files with MSYS2 UCRT64 `bin` prepended to PATH, `CC` set to `C:\msys64\ucrt64\bin\gcc.exe`, TEMP/TMP=`D:\Temp\merit-gcc\tmp`, and D: base temp | **36 passed in 10.15s** | Configured native baseline for current borrow tests; no hypothetical syntax tested. |
| Same focused files on synchronized PR #139 main (`8030d10`) with the configured Windows toolchain and D: temp | **36 passed in 9.06s** | Current Alpha.2 borrow baseline before the design-only PR #140 update. |
| In-memory Lark grammar alternatives plus `Checker(parse(...)).check()` of old `borrow` identifiers | Preferred form and three old forms parsed under contextual prototype; naive alternative failed old type; old programs accepted by current checker | Syntax compatibility investigation only; no production parser change. |

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
