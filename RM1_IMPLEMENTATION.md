# RM1 immutable local borrow implementation ledger

**Status:** In progress. PR #141 is a merged, fail-closed parser checkpoint.
This ledger tracks the continuation PR. The normative contract remains
[`LOCAL_BORROW_CONTRACT.md`](docs/design/alpha3/LOCAL_BORROW_CONTRACT.md).
The parser checkpoint must not be described as a working stored-borrow feature.

## Verified merged baseline

PR #141 merged on main as `bb6bd152e255d081edcd39f87a04f3b371acf016`.
The merge changed the reference parser, AST node/binding assignment, one
explicit checker rejection, tests, and RM0 closure documentation. It did not
change the native compiler, artifact formats, interpreter, C emitter, or public
project interface. The new syntax produces a distinct local-borrow node and
origin binding; checker diagnostic `M5400` stops it before execution or codegen.

| Audit on merged main | Result |
| --- | --- |
| Existing `borrow` type, local identifier, and parameter forms | Parser/checker focused coverage passed. |
| Existing borrowed-return diagnostics and interpreter/native behavior | Focused borrowed-return suite passed. |
| New syntax reaching backend without proof | Blocked by `M5400`; no silent acceptance. |
| Canonical fast regression gate | `MERIT_GATE_RESULT=PASS`, 93 tests in 12.33s. |
| Focused syntax and borrow suite | 41 passed in 11.27s. |

No Alpha.2 regression is confirmed by this bounded audit. It does not replace
the full Alpha.2 corpus or final RM1 gates. Test log:
`D:\Temp\merit-tests\rm1-merged-fast.log` (outside the repository).

## Capability and evidence matrix

| Boundary | Required evidence | State |
| --- | --- | --- |
| Contextual source syntax and old `borrow` names | Preferred declaration parses; old names and borrowed parameters remain valid; comments/newlines covered. | Parser checkpoint merged. |
| Checker origin, authority, and final use | Accept 01, 02, 04, 07, 09, 18, 24; reject 05, 06, 08, 22, 23, 28; unknown origin/effects/control flow fail closed. | Open. |
| Ownership and cleanup | No borrow destructor; owner drop/move/replace, early/error cleanup, and allocator provenance remain exact. | Open. |
| Interpreter and C | Accepted programs have output and cleanup parity; single evaluation and no public ABI change. | Open. |
| HIR/MIR v2 | Explicit local-loan effects, strict schema/record validation, deterministic bytes; v1 old bytes unchanged and old reader rejects v2. | Open. |
| Native v5 and public project interface | Complete versioned MIR/C/header framing, strict transport/manifest validation, v4 old bytes unchanged, no Python fallback. | Open. |
| Merit-native compiler and stage 1/2 | Accepted/rejected and diagnostic parity; fresh public compiler stages produce equivalent artifacts. | Open. |
| Gates | Focused, subsystem, self-hosting, final Windows/Linux full gates on final tree. | Focused baseline only. |

## Bounded semantic-coherence audit

For each new accepted case, compare one source program at every available
boundary: parser binding IDs and spans, checker decision and diagnostic, HIR
loan identity, MIR create/use/end and cleanup effects, interpreter trace,
generated C/header, replacement bundle/protocol, fresh stage-1/stage-2
artifacts, and public project execution. Reject missing or contradictory facts
at the first boundary; do not repair them by a Python fallback or by weakening
an Alpha.2 test. Freeze representative old-program artifact digests and old
diagnostics before v2/v5 changes, then compare them after each coherent family.
This audit is deliberately limited to the approved local immutable borrow;
R4–R8 and the unrelated generic-vector gap remain separate.
