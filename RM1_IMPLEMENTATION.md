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
| Checker origin, authority, and final use | Accept 01, 02, 04, 07, 09, 18, 24; reject 05, 06, 08, 22, 23, 28; unknown origin/effects/control flow fail closed. | Python reference checker: 7/7 accepted and 6/6 rejected cases pass. Native parity open. |
| Ownership and cleanup | No borrow destructor; owner drop/move/replace, early/error cleanup, and allocator provenance remain exact. | Checker/ownership planner verifies owner-only implicit cleanup; execution traces open. |
| Interpreter and C | Accepted programs have output and cleanup parity; single evaluation and no public ABI change. | Python reference interpreter/C parity passes 7/7 accepted cases plus borrowed-parameter and owner lifecycle traces. Native replacement parity open. |
| HIR/MIR v2 | Explicit local-loan effects, strict schema/record validation, deterministic bytes; v1 old bytes unchanged and old reader rejects v2. | Versioned Python contract objects, strict v2 readers, canonical round trips, and malformed-record tests pass. A bounded checked-source i32 producer emits create/use/end and post-final-use assignment; required-case completeness and native producer parity remain open. |
| Native v5 and public project interface | Complete versioned MIR/C/header framing, strict transport/manifest validation, v4 old bytes unchanged, no Python fallback. | Python transport and public artifact publication/loading accept validated v5 MIR v2, reject mixed snapshot framing and mislabeled v4/v5. Merit-native producer and actual new-feature project build remain open. |
| Merit-native compiler and stage 1/2 | Accepted/rejected and diagnostic parity; fresh public compiler stages produce equivalent artifacts. | The statement frontend now retains contextual local-reference mode separately from its declared referent type. The native driver explicitly rejects that mode until loan proof and v5 emission exist. No accepted local-reference program reaches the native backend yet. |
| Gates | Focused, subsystem, self-hosting, final Windows/Linux full gates on final tree. | Focused baseline only. |

Current focused RM1 checker, execution, compatibility, source-artifact, and
HIR/MIR contract checkpoint: 185 passed in 11.96 seconds on Windows. This is
not a subsystem, self-hosting, or full-gate result.

### Checker checkpoint

The Python checker now proves a fixed last use for each known function-local
reference in straight-line statement order, including existing linear
`with capability` blocks. It tracks reference and origin by binding ID,
rejects owner write/move/drop/replace or mutable ephemeral borrow until the
final reference use, and permits those operations afterward. Two shared loans
may coexist. Borrowed-parameter origins and proven non-retaining shared-borrow
calls are supported. Invalid origin, direct local-reference escape, unsupported
branch/loop/match flow, and uncertain `ByteSlice` backing-owner validity fail
closed. Reference bindings do not enter the owner cleanup list. Interpreter
and C generator entry deliberately reject feature-bearing programs with
`M5400` until the next coherent execution slice is implemented. This checker
checkpoint alone is **not a working RM1 feature**.

### Reference execution checkpoint

The interpreter now binds a local reference to the exact owner `TypedValue`
object without adding an owned cleanup entry. The C generator emits a local
`const T *` pointer and dereferences it for value reads, while passing its
address directly to existing shared-borrow parameters. This pointer is an
internal lowering choice, not a public reference type. Focused parity tests
pass for all seven accepted cases and for normal, explicit-drop, moved-owner,
replaced-owner, and early-return destructor traces. `try` error propagation
remains explicitly rejected by the checker when a local loan appears; its
control-flow proof is outside this straight-line checkpoint. HIR/MIR v2 and
native v5 remain mandatory before RM1 can merge.

### Versioned contract checkpoint

`bootstrap-hir-v2` now has an explicit non-owning local-reference binding and
source-anchored origin record. `bootstrap-mir-v2` has explicit create/use/end
effects tied to declared reference/origin source bindings, instruction IDs,
immutable permission, and spans. V2 readers reject unknown semantic fields at
each nested object boundary, unknown IDs/effects/permissions, inconsistent
origins, duplicate or unordered events, and missing end effects. V1 readers
reject new-feature fields and modes; old serializers retain their v1 shape.
Focused contract, checker, and reference execution suites pass 146 tests on
Windows. Source lowering does not yet produce these v2 records, and the native
replacement compiler does not yet consume or emit them; this remains an
interchange-contract checkpoint rather than complete canonical representation
evidence.

The generic checked-HIR-to-MIR bridge now lowers v2 local-reference
initializers into a direct borrow instruction and derives ordered create,
read/call-use, and final-use end effects from the emitted instruction IDs.
It rejects a mismatched origin and unsupported structured control flow.
The ABI bridge retains the v2 loan records. Focused HIR-to-MIR and ABI tests
pass 43 tests on Windows. This bridge consumes constructed checked HIR; it is
not yet evidence that the Python source frontend or Merit-native project
compiler emits v2 from actual source.

The first Merit-native source probe failed with driver status 1053. This is
the type-catalog unresolved-type status: the statement parser had represented
`borrow` as the declared type in `let r: borrow T`, losing the reference mode
and `T`. The statement frontend now emits distinct contextual mode and
referent-type operands, with matching record counts. A focused native and
interpreter operand test passed, an existing Alpha.2 operand fixture passed,
and two public-interface native-driver probes remain fail-closed pending the
native loan checker. These are parser/transport observations only, not native
RM1 semantic acceptance or v5 production evidence.

The Merit-native source-record layer now derives a separate local-loan origin
catalog from actual parsed statements. It assigns dense reference and owner
binding identities using the existing scope-aware resolver, accepts multiple
shared references and a borrowed-parameter origin, and rejects missing,
reference-valued, or mutable-reference origins at this boundary. A single
focused test compares the same six source probes through the Merit interpreter
and generated native executable. This catalog is not yet a final-use proof;
the production driver continues to reject every local-reference program.
The source ownership catalog now marks a local reference as non-owning even
when its referent type is owned. A focused interpreter/native probe asserts
that an owned `Box` origin retains cleanup authority while its `borrow Box`
binding has none; the existing Alpha.2 derived-ownership fixture also passes.
The same source catalog now derives ordered reference-use positions and a
proven final-use position for each resolved local loan. The focused native and
interpreter probe covers one loan, two simultaneous shared loans, a borrowed
parameter origin, and malformed/out-of-order or unknown-use rejection before
any end record is emitted. This establishes source-backed create/use/end
identity; owner-effect conflicts, call effects, escape checks, and emission
into canonical HIR/MIR v2 remain open. The native driver remains fail-closed.
An initial Python-oracle checked-source producer now emits HIR v2 and MIR v2
for a narrow straight-line i32 local-loan function with a proven borrowed
single-argument call. It derives binding IDs and spans from parsed source,
emits ordered create/use/end effects, round-trips through both canonical
readers, rejects invalid source before artifact creation, and fails closed on
accepted source outside its representable subset. The 113 focused source and
contract tests pass. This is partial source-to-v2 evidence, not complete
coverage of the seven required cases and not a Merit-native v5 producer.
The checked-source MIR v2 bytes also survive v5 project-artifact transport
encoding and strict decode in a focused test. The test uses sentinel C/header
bytes solely to exercise framing; it is not a native C producer or a complete
public project bundle parity claim.
The same bounded source producer now preserves an owner assignment after a
stored reference's final call use. Its emitted MIR places the loan end before
the assignment; moving that assignment before the use is rejected by M5402
before artifact emission. This is focused effect-order evidence only.
The producer also round-trips two simultaneous shared loans with separate
final uses. An owned `String` source probe exposed an existing gap in the
generic HIR-to-MIR `let` bridge: it emits a copy for the initializer and does
not establish source owner cleanup. The bounded source producer therefore
rejects owned `String` rather than presenting incomplete ownership effects
as valid v2 evidence. Complete owned-value movement and cleanup lowering is
required before extending this source path to cases 01, 02, 07, and 09.
The generic HIR-to-MIR bridge also now rejects an owned `let` initializer in
v2 rather than lowering it as a copy. This is a v2-only safety guard; the
existing v1 bridge tests and canonical contract tests remain green (136
focused tests). A complete move and cleanup plan is required before lifting
the guard.
The v2 MIR reader now rejects an implicit `copy` whose source or destination
is an owned local in a loan-bearing function, including directly supplied
artifacts that bypass HIR lowering. Focused contract/bridge tests pass. This
does not change v1 decoding or supply the missing owned move/cleanup producer.
Loan-bearing MIR v2 functions now also reject non-straight-line control flow
at decode time. The current final-use proof has no branch or loop joins, so
accepting such a supplied artifact would overstate its safety. The focused
MIR/bridge regression suite passes 90 tests.
The native explicit-owner-effect pass now rejects owner assignment, drop,
replacement, and owned binding transfers before the last reference use; it
permits those operations after final use, multiple shared readers, a copy
read of a primitive owner, and the accepted capability-scope ordering. Eleven
source probes pass through both interpreter and native execution. This pass
does not prove calls, escapes, or unsupported control flow, and is not wired
to enable production compilation; those are mandatory before the 907 native
fail-closed guard can be removed.
The next native source pass validates a direct one-argument call only when a
resolved signature proves a borrowed parameter and a value return. It rejects
owned/retaining or unknown calls, direct return and aggregate escapes,
reference destruction, nested calls with unknown effects, and unsupported
branch/loop/match flow while a loan exists. Eleven focused source probes match
between the Merit interpreter and native executable; the two public driver
fail-closed regressions still pass. The pass is intentionally conservative:
copying a primitive referent into a new local, field-value returns, and safe
ephemeral borrowed calls involving the owner need separate proof before RM1
can claim the complete approved semantic surface. It is not yet connected to
the production artifact path or to stable M54xx diagnostics.
The source use pass also admits a direct, proven borrowed-parameter read of
the owner while a stored shared loan remains live. A mutable borrowed call
on that owner remains a conflict. The focused interpreter/native source
probe covers both outcomes; this does not lift the production driver guard.
The native source-record layer now has one proof entrypoint composing origin,
use, final-use end, owner-effect, and reference/call checks in that order. It
returns a named failure stage plus the existing pass-specific detail code and
never reports success for a source with no local loan. A focused 75-second
interpreter/native probe covers success, a live-owner conflict, and an
unknown call. The driver still rejects RM1 source until native v5 emission
and complete diagnostic parity are implemented.

The native project-artifact transport now recognizes a separate v5 version
word, requires a complete v2 MIR/C/header set, validates v2 MIR framing and
loan effects, rejects legacy snapshot mixing, and records the v5 producer
protocol in the public manifest. Loading rejects v2 MIR mislabeled as v4.
The old v4 producer protocol and bytes retain their existing path. Focused
transport/preparation tests pass 36 tests on Windows. This is reader and
publication support; no Merit-native compiler emits a v5 bundle yet.

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

Current bounded findings:

| Classification | Finding | Boundary |
| --- | --- | --- |
| No issue | The required straight-line checker matrix proves shared reads, final-use owner effects, and specified live-loan rejection with binding-ID origins. | Reference parser/checker. |
| Future architectural risk | `ByteSlice` has a separate backing-owner relationship; a local loan of the slice alone does not prove that backing storage remains valid. The checker rejects that new combination until a separate origin proof exists. | Checker and future MIR provenance. |
| No issue | A local reference is absent from owned cleanup records; the owner remains the only destructor authority. | Ownership planner. |
| Confirmed implementation gap, merge-blocking | Reference interpreter/C lowering passes focused new-feature parity, but HIR/MIR v2, native v5, replacement compiler, and stage parity remain absent. | Canonical representation and production replacement compiler. |
| Confirmed required-path defect, narrowly corrected | A pre-feature program `fn inspect(borrow x:i32)->i32 { return x; }` passed the checker but emitted `_merit_result = x;` where `x` is a pointer. RM1's required case 24 passes a stored local reference to such a function, so native execution could not satisfy the approved acceptance matrix. The reference C emitter now dereferences only a direct borrowed parameter returned from a value-returning function; borrowed-return functions and other old emission paths remain unchanged. Focused old-source and RM1 execution regressions pass. This changes the previously invalid C bytes for that one old source shape. Representative runnable Alpha.2 fixture digests pass. | Reference C emitter and case 24 execution. |

Representative old-program C/header digests were compared byte for byte
against the committed pre-fix compiler for scalar, owned/destructor, and
borrowed-return fixtures. All three pairs match and are pinned in
`tests/test_alpha3_local_borrow_compatibility.py`. Existing HIR v1 and MIR v1
sample canonical JSON digests are pinned in their contract tests. The focused
compatibility/contract/execution run passed 128 tests on Windows. This is
representative byte evidence, not yet the complete Alpha.2 artifact corpus.
