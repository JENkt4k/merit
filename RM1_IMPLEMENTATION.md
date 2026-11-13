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
| Checker origin, authority, and final use | Accept 01, 02, 04, 07, 09, 18, 24; reject 05, 06, 08, 22, 23, 28; unknown origin/effects/control flow fail closed. | Python reference checker: 7/7 accepted and 6/6 rejected cases pass. Native source-record proof: matching 7/7 and 6/6 stage outcomes in interpreter/native probe; production diagnostic and artifact parity open. |
| Ownership and cleanup | No borrow destructor; owner drop/move/replace, early/error cleanup, and allocator provenance remain exact. | Checker/ownership planner verifies owner-only implicit cleanup; execution traces open. |
| Interpreter and C | Accepted programs have output and cleanup parity; single evaluation and no public ABI change. | Python reference interpreter/C parity passes 7/7 accepted cases plus borrowed-parameter and owner lifecycle traces. Native replacement parity open. |
| HIR/MIR v2 | Explicit local-loan effects, strict schema/record validation, deterministic bytes; v1 old bytes unchanged and old reader rejects v2. | Versioned Python contract objects and strict v2 readers pass. The bounded checked-source producer covers all 7 required accepted cases and stops all 6 required rejected cases before artifact emission. Complete project lowering and native producer parity remain open. |
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
The v2-only HIR `print` node now carries an actual final local-reference read
from source to MIR without changing v1 HIR bytes or allowing the node in v1.
Focused source tests cover case 04's print before owner assignment and case
24's proven call followed by a final print, with ordered use/end effects.
The source/contract/bridge suite passed 150 tests at this checkpoint.
The bounded producer now also lowers case 18's capability scope, including
its explicit MIR capability check and a final loan end before the later owner
write. The focused representation suite passed 151 tests at that checkpoint;
complete project source-to-v2 lowering remains open.
The same bounded source producer now preserves an owner assignment after a
stored reference's final call use. Its emitted MIR places the loan end before
the assignment; moving that assignment before the use is rejected by M5402
before artifact emission. This is focused effect-order evidence only.
The producer also round-trips two simultaneous shared loans with separate
final uses. The v2 HIR-to-MIR bridge now moves a top-level owned `String`
literal into its owner and emits exactly one owner drop at explicit drop or
function return, after the proven loan end. It rejects unsupported owned
initializers, owned calls and moves without transfer proof, scoped owned
initialization, duplicate drops, and owned returns. V1 lowering and canonical
bytes remain unchanged. The producer also lowers the required single-field
`Box` case 07: a primitive field read ends the loan, then the owner moves
to `y` and only `y` is dropped. Reordered moves before loan creation or final
use are rejected. All seven required accepted and six required rejected
cases now have source-to-v2 tests. The combined focused RM1 checker,
interpreter/C execution, compatibility, source artifact, and HIR/MIR bridge
checkpoint passes 213 tests in 11.87 seconds on Windows. This does not
replace subsystem or self-hosting gates.
The v2 MIR reader now rejects an implicit `copy` whose source or destination
is an owned local in a loan-bearing function, including directly supplied
artifacts that bypass HIR lowering. Focused contract/bridge tests pass. This
does not change v1 decoding; the bounded v2 source producer now uses explicit
moves and exactly-once cleanup for its supported owned `String` and `Box` cases.
Loan-bearing MIR v2 functions now also reject non-straight-line control flow
at decode time. The current final-use proof has no branch or loop joins, so
accepting such a supplied artifact would overstate its safety. The focused
MIR/bridge regression suite passes 90 tests.
HIR v2 loan and MIR v2 effect readers now reject empty source spans (122
focused representation tests pass). Full out-of-range span validation still
needs source-unit identity at the project artifact boundary: the standalone
v5 transport contains MIR/C/header bytes but no source bytes or per-function
source-unit key. The native producer must validate spans against the source
unit it compiled; project-load validation cannot infer that unit solely from
the current standalone transport. This is an evidence gap, not permission to
accept invalid spans.
The v2 MIR reader now also checks owner operations against every loan's
create-to-final-use interval. It rejects owner drop/move/deallocation,
binding or field writes, unproven owner calls, and mutable borrows while a
loan is live; an owner drop after the end record remains valid. The focused
MIR/source bridge suite passes 98 tests. A shared borrowed call on the owner
requires explicit non-retaining call metadata before the v2 decoder can
accept it; the current reader fails closed for such a call.
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
The same focused probe now exercises the full required RM1 source matrix
(accepted 01/02/04/07/09/18/24 and rejected 05/06/08/22/23/28) through the
composed native proof. All expected success/failure stages match in the Merit
interpreter and generated native executable (one project test, 91.60 seconds).
This is source-record proof evidence, not production compiler acceptance or
stable M54xx diagnostic parity.
The native origin catalog now checks that a local reference's declared
referent type matches its local owner declaration. For a borrowed parameter
origin, it compares the resolved built-in type code; an unrepresented custom
parameter type fails closed until catalog support is added. The focused
interpreter/native probe rejects an `i64` reference to an `i32` owner and
retains the valid borrowed-parameter case (1 test passed in 77 seconds).

The native project-artifact transport now recognizes a separate v5 version
word, requires a complete v2 MIR/C/header set, validates v2 MIR framing and
loan effects, rejects legacy snapshot mixing, and records the v5 producer
protocol in the public manifest. Loading rejects v2 MIR mislabeled as v4.
The old v4 producer protocol and bytes retain their existing path. Focused
transport/preparation tests pass 36 tests on Windows. This is reader and
publication support; no Merit-native compiler emits a v5 bundle yet.

The loan-bearing MIR v2 reader now checks the straight-line lifecycle of
source-bound owned locals: each must be initialized by a proven move and
subsequently transferred or dropped exactly once before return. It rejects
use after move/drop and missing cleanup. This is deliberately limited to the
current straight-line v2 contract; it does not claim full control-flow or
native-producer proof. The focused source-artifact, MIR-contract, and Alpha.2
compatibility suite passed 102 tests on Windows.

The production native driver now invokes the composed source-loan proof after
its callable catalog is available, using the current function's parameter
range and independently derived ownership bindings. It retains status 907
even for a successful proof until native v2/v5 emission is connected; old
sources do not enter this branch. The 45-module bootstrap compiler builds,
and its interpreter/native regression passed. A temporary, subsequently
restored cutover on the smallest `i32` stored-borrow program reached native
driver status 4368 after the proof boundary. Isolated status-base probing
identified this as assembly status 3368: source-token assembly +1000,
source-type assembly +1000, semantic function +200, body +100, expression
failure 68. In `mir_source_function_records.mrt`, the `borrow x` initializer
reaches `sfr_emit_expression` and is not represented, so the body returns its
unknown-expression status. The v1 assembly therefore cannot be used as a v2
producer; removing 907 now would not publish a valid artifact. The next
implementation boundary is native local-reference expression/body lowering,
then loan-aware canonical MIR and C emission, followed by v5 framing.

The native source-body and structured-placement path now has distinct RM1
local-reference and borrow-create records. It retains binding/origin IDs and
referent type, and the ownership-control pass records no owner move or cleanup
for the reference. The proof's temporary ownership catalog is separate from
the assembly output. A focused interpreter/native source-record test passed,
and an isolated post-proof cutover now reaches canonical MIR validation status
4101: the v1 validator correctly rejects the new kinds. Production still
returns 907. Native v2 MIR/C/header emission and v5 publication remain open.
The native flat-record validator now has an explicit local-borrow version path:
the legacy validator rejects RM1 local-reference and borrow-create records,
while the v2 validator accepts the same well-formed stream. The focused
interpreter/native record regression passes. The production canonical writer
still invokes the legacy validator and remains guarded by 907; this validator
change alone does not authorize artifact publication.

The first bounded production cutover now publishes a complete v5 artifact for
one straight-line immutable `i32` local reference with a single `print` use.
The same native driver uses v1 validation and v4 framing for old programs,
while a successful composed source proof selects v2 validation and a native
MIR v2 writer with ordered create/use/end effects. The reference local is
non-owning in MIR and C; C stores its address and dereferences it for the
proven read. The project request path emits native MIR, C, and header, and the
public prepare/load/build path strictly decodes, compiles, and executes the
v5 bundle with output matching the Python interpreter. Repeated native
requests produce identical transport bytes. A multiple-reference program
still fails closed with status 907 before artifact publication. The focused
v5/native-record suite passed 2 tests in 64 seconds, and the existing v4
artifact regression passed in 91 seconds alongside the v5 test.

This cutover is deliberately narrower than RM1 completion. The native v2
writer currently supports one reference and one direct `print` use; other
loan shapes retain 907. The required seven accepted and six rejected cases
have not yet passed through the public native interface. The Python oracle
and native MIR agree structurally for this program after accounting for the
project request's 13-byte canonical module prefix and compiler-private
temporary names; raw source offsets and temporary spellings are not claimed
byte-identical across those two different source inputs. Native HIR v2
publication, borrowed calls, owner operations after final use, exact M54xx
diagnostics, full matrix coverage, stage parity, and broad gates remain open.

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

## Native public-case burn-down (in progress)

The grouped public-producer probe on the current RM1 branch reached these
boundaries. A zero status only counts as an accepted case after strict v5
decode, generated C compilation, execution, and interpreter comparison.

| Required case | Public native boundary | Next shared mechanism |
| --- | --- | --- |
| Accept 01, 04, 18 | v5 decode, C build, and execution pass | Preserve old artifact bytes. |
| Accept 02 | One-reference MIR loan writer fails closed | Ordered effects for multiple shared loans. |
| Accept 07 | Native C function emission rejects aggregate reference | Aggregate field access and ownership transfer after final use. |
| Accept 09 | Backend catalog rejects explicit owner drop | Exact owner cleanup and drop emission. |
| Accept 24 | v5 decode, C build, and execution pass with the helper before `main` | Compare canonical effects and diagnostics across stages. |
| Reject 05, 06, 08, 22, 23, 28 | Rejected before artifact publication with status 907 | Stable M54xx identity, span, and note transport. |

The same borrowed-call body works with its helper before or after `main`.
The production driver now applies the existing native loan proof once per
local-borrow function after project-wide catalog derivation. Previously the
proof lived inside the first-function-only catalog block, so later functions
could reach MIR emission without loan records. A preceding unrelated helper
also reproduced this issue. A later-function conflicting owner write is now
rejected before artifact publication. Native C now
handles a stored `String` reference in `print` and a non-retaining borrowed
`i32` call/return, while preserving borrowed-return functions and old value
emission. The focused v5 and legacy v4 project tests passed together (2 tests,
93 seconds). The PR remains draft; stage and broad gates are still open.
