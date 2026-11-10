# RM0 first-slice local-borrow contract for review

**Status:** Owner-approved R1–R3/R9 semantic direction, proposed normative
wording and encoding contract for review in PR #140. This document does not
freeze RM0 or authorize production compiler changes. The first implementation
PR may begin only after the design-only PR is reviewed and merged. See the
[implementation audit](LOCAL_BORROW_IMPLEMENTATION_PLAN.md) and
[case analysis](BORROW_MODEL_CASES.md).

## Relationship and source form (R1)

The first new relationship is an **immutable function-local stored borrow**.
A local reference binding is non-owning and semantically distinct from an
owned value of type `T`. It holds read access to one proven addressable owner
or borrowed parameter, without receiving transfer or destruction authority.
It can read `T` and satisfy an existing compatible, proven non-retaining
`borrow T` parameter. It cannot satisfy a value `T` parameter, be returned,
enter an aggregate/vector/enum, or otherwise escape the permitted local
lifetime. This does not define general reference types, generic substitution
for references, or a public reference ABI.

**Preferred provisional spelling:** `let r: borrow T = borrow x;`. The current
grammar's `let` accepts a value `type_ref` and its expression grammar has no
borrow expression, so this form is not yet executable. An in-memory LALR
probe added a dedicated local-borrow declaration without changing production
code. It parsed the preferred form and existing borrowed-parameter and
`borrow`-named local forms. A *naive* literal-keyword alternative rejected an
existing accepted program with `struct borrow` and `let x:borrow = ...`;
the in-memory contextual-token probe preserved that program. Thus the
preferred spelling has a concrete lexical compatibility hazard, but no
demonstrated unavoidable grammar conflict. Implementation must regression
test `borrow` as an old type and binding name, comments/newlines between tokens,
and the existing accepted/rejected parser corpus before choosing a lexer
strategy. No substitute spelling is approved here.

## Validity, permission, final use (R2)

F keeps three facts separate: whether the origin resource is valid, who may
read/write it, and who may move/destroy it. Creation of an immutable local
reference grants shared-read access only. Multiple shared reads may coexist;
exclusive write conflicts with any live shared loan. The origin must remain
valid at every possible use. A-style analysis ends restrictions after the last
possible use on each supported path; the reference may remain lexically in
scope after that point. An otherwise legal owner mutation, move, replacement,
or drop after proven final use must be accepted. Unknown origin, hidden later
use, retaining or unknown-effect call, unsupported control flow, or escape
fails closed. No runtime borrow checking is introduced.

The first implementation's minimum is straight-line, known single-place
provenance. It may conservatively reject joins/loops/reassignment or projected
places outside this minimum. It may borrow a known borrowed parameter without
extending the parameter's lifetime. Existing ephemeral borrowed returns do
not become storable through this rule; relay through a local reference remains
deferred.

| Case IDs | Required outcome under stated assumptions |
| --- | --- |
| 01, 02 | Accept one or two immutable local reads; origin lives through all uses. |
| 04 | Accept owner mutation after proven final reference use, even in the same lexical scope. |
| 07 | Accept owner move/transfer after proven final reference use. |
| 09 | Accept one owner drop after proven final reference use. |
| 18 | Accept owner mutation after the borrow's lexical block ends. |
| 24 | Accept a known non-retaining shared-borrow call followed by a local read. |
| 05, 06, 08 | Reject owner write, move, or drop when a later reference use is possible. |
| 22, 23 | Reject return of a local reference and aggregate-held reference escape. |
| 28 | Reject owner replacement when a later reference use is possible. |

Attempted value-parameter transfer, later use after invalidation, unknown
origin, and overlapping Alpha.2 mutable borrow also reject. These are safety
results, not permission to weaken existing Alpha.2 diagnostics. Cases outside
the minimum retain the conditional/deferred status in the case analysis.

## Ownership and cleanup (R3)

Borrow creation, use, and end never move ownership. The local reference has
no independent destructor or allocator. The owner remains responsible for
exactly one cleanup, including implicit normal return, early return, error
propagation, `drop`, `replace`, and custom destructor order. A live loan blocks
an operation that could invalidate its origin; after final use the ordinary
Alpha.2 owner operation runs with its existing trace. Borrow creation itself
does not allocate or require a capability. An owner and its release provider
must remain valid through all uses. Physical address stability is an
implementation obligation during a live reference, not a new public pinning
or ownership relationship.

## Diagnostics and versioned representation (R9)

The observable diagnostic **identities** are `invalid-local-borrow-origin`,
`conflicting-live-loan`, `invalid-local-reference-use`, and
`forbidden-local-reference-escape`. Implementations assign specific named
codes at the canonical diagnostic definition site. The primary span is the
invalid origin expression, conflicting owner operation, invalid reference
use, or escaping expression respectively. A conflict/invalid-use diagnostic
includes a note pointing to the borrow creation or relevant owner consumption
site where available. The same source must produce equivalent category,
primary span, and notes in the Python oracle and replacement compiler.
Old source retains its existing diagnostic codes, spans, and wording.

The following is the **reviewed representation recommendation**, not a claim
that these encodings already exist. The owner must still review and merge this
design PR before implementation:

| Artifact | Old-program contract | New-feature contract |
| --- | --- | --- |
| Typed HIR | Existing `bootstrap-hir-v1` bytes unchanged. | Explicit `bootstrap-hir-v2` local-reference binding mode and origin/place identity; reject unversioned or malformed new fields. |
| Canonical MIR | Existing `bootstrap-mir-v1` bytes unchanged, including old borrow and returned-origin meaning. | Explicit `bootstrap-mir-v2` local-loan effect records for create, read/call use, and end; each anchors a reference binding, origin binding/place, permission, ordered instruction ID, and source span. Do not reinterpret an Alpha.2 ownership mode or discriminant. |
| Native project artifacts | Existing complete v4 MIR/C/header bundle and producer protocol bytes unchanged for projects without a local borrow. | A distinct v5 bundle/protocol for any project containing the feature. Its canonical MIR uses v2; old decoders reject v5, new decoders accept validated v4 and v5. No Python semantic fallback. |
| C and public ABI | Old generated C/header/layout bytes and public signatures unchanged. | Local references are internal implementation values; no new public C parameter, field, or layout in this slice. New C/header output is deterministic and compared with the independent oracle. |

### Why a version transition is required

The existing HIR and MIR readers require exact `bootstrap-hir-v1` and
`bootstrap-mir-v1` schema values, but their JSON parsers read known fields and
do not reject every unknown key. An extension object under either v1 schema
could therefore be silently ignored by an old reader while changing the
program's meaning. The v4 native transport has a fixed three-artifact tail
(MIR, C, header), checks lengths, and rejects trailing data. Its old decoder
requires bundle version 4 exactly. There is no evidenced optional,
must-understand extension slot in v1 or v4. A versioned extension section
would still need a new outer version and strict old/new decoding, while adding
another framing and ordering rule. It has no demonstrated compatibility or
implementation advantage for this one relationship. Retain conditional HIR
v1/v2, MIR v1/v2, and native v4/v5. An old decoder must reject a new-feature
artifact at the outer schema/version boundary before interpreting any payload.

The compatibility change crosses four implementations/boundaries: (1) the
Python oracle gains new HIR/MIR validation and differential output while its
v1 encoders remain byte-identical; (2) the Merit-native replacement producer
gains v2 local-loan semantics and conditional v5 emission; (3) fresh stage-1
and stage-2 compilers must independently emit the same v5 protocol and
canonical bytes, without Python semantic fallback; and (4) the public project
prepare/load/build interface must recognize validated v5 beside v4 and retain
the v4 manifest/request/artifact behavior for old projects. This is one new
version at each of three representation layers, not a new public C ABI.
Existing v4 preparation dispatches on bundle version; its transport reads
exactly three length-delimited artifacts, and the project loader checks the
producer protocol and request digest. V5 therefore needs an explicit
transport dispatch, protocol identity, manifest validation, and content
digest checks; a v5 producer must not be mistaken for v4 or trigger the legacy
snapshot path. The project-request format may remain unchanged if it can
carry the source and exports without ambiguity; change it only on demonstrated
need, with its own version and old-reader rejection.

For a v5 project, every encoded function/module must be framed and validated
under the new version, including unchanged modules in that project. Local-loan
records are ordered by source-established function order, then instruction
order, then semantic binding ID. IDs are stable under identical source. A
record must refer to a declared reference binding and valid origin/place;
create precedes use, use precedes end, and no use follows end. Duplicate IDs,
unknown permission/effect kind, missing end, out-of-range span, inconsistent
origin, truncated length, trailing data, mixed v4/v5 framing, or v2 data
inside a v4 declaration must fail closed. The decoder must not guess a
legacy interpretation. V2 HIR/MIR readers must reject unknown semantic fields
and unsupported versions; v1 readers must reject v2 by schema. The v5
transport reader must reject unknown sections, invalid UTF-8, invalid byte
values, inconsistent lengths, and unexpected end/trailing data. V4 readers
must reject v5 at the version word. Conditional v4/v5 emission retains
old-program artifact bytes, including the manifest, protocol, canonical MIR,
C, and header.

Minimum migration evidence: freeze representative Alpha.2 HIR/MIR/v4/protocol/
manifest/C/header byte digests and assert unchanged results for old accepted
programs; assert old HIR/MIR/v4 readers reject v2/v5 artifacts; round-trip and
corrupt every new length, schema, section, effect, ID, span, and digest;
compare accepted/rejected diagnostics and primary/note spans across Python,
native replacement, stage 1, and stage 2; compare deterministic HIR/MIR/C/
header/protocol bytes across repeated fresh builds and source-order variants;
and compare normal, early, error, explicit-drop, and replace cleanup traces
with the Alpha.2 oracle. The public project interface must accept a complete
v5 build and reject a stale or partial one without fallback. New-feature C
may change; old-program C/header and public ABI/layout may not.

No old numeric semantic identifier is reused. New effect and diagnostic
values must be named at their canonical definition boundaries. The compiler
implementation may choose internal algorithms, record layout, and numeric
assignments within this observable contract.

## Deferred relationships and approval boundary

R4–R8 are explicitly deferred: Shared/Weak, regions, pinning, foreign
ownership/callbacks, array/tensor views, concurrency, thread transfer, and
their runtimes. The local reference has no inferred sendability, shareability,
thread affinity, stored aggregate lifetime, or async capture right. The
`Vec<Sample>` replacement gap and owned indexed extraction are separate.

This design review recommends the diagnostic identity and conditional
v1/v2/v4/v5 compatibility contract above. No code, syntax, ABI, or feature is
implemented merely by this document's existence.
