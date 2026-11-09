# Merit Memory & Resource Model

**Status:** Proposed design --- not yet a language specification\
**Draft:** 0.1\
**Date:** 2026-09-28

> **Design objective:** Make resource relationships explicit enough for
> strong static guarantees, without requiring every safe program to
> conform to a single universal ownership topology.

------------------------------------------------------------------------

## 1. Executive summary

Merit should treat memory management as one instance of a broader
**resource-lifetime problem**.

Heap allocations, files, sockets, locks, mappings, GPU buffers, database
transactions, foreign handles, and other resources differ in
implementation, but share three fundamental questions:

1.  **Who controls the resource?**
2.  **Who may access it?**
3.  **When and how must it cease to exist?**

This proposal defines four primary relationship forms:

``` text
Owned<T>
Borrowed<T>
Shared<T>
Weak<T>
```

and leaves room for explicit **regions/arenas** and **hazardous/foreign
capabilities**.

The compiler should statically enforce properties that follow from those
declarations. Runtime machinery should be introduced only when the
selected relationship intrinsically requires it---for example, ownership
accounting for `Shared<T>`.

Merit's target is therefore not simply "Rust with different syntax."

It is:

> **Explicit resource topology + deterministic semantics + selective
> static enforcement + explicit hazardous escape hatches.**

### 1.1 Design-space comparison

  ------------------------------------------------------------------------
  Model             Primary mechanism Cost accumulates  Characteristic
                                      primarily in      tradeoff
  ----------------- ----------------- ----------------- ------------------
  C / unmanaged     Manual allocation Programmer,       Maximum freedom;
                    and lifetime      testing,          weak default
                                      debugging         guarantees

  C++ / RAII        Scope             API complexity +  Deterministic
                    destruction +     programmer        cleanup, but
                    library                             unsafe states
                    abstractions                        remain
                                                        representable

  Java / C#         Managed           Runtime + memory  Strong memory
                    references +                        safety;
                    tracing GC                          nondeterministic
                                                        reclamation

  Reference         Per-reference     Runtime           Deterministic
  counting          ownership         operations        reclamation;
                    accounting                          cycles and atomic
                                                        cost

  Rust              Ownership +       Compiler +        Strong static
                    borrowing +       programmer model  safety; ownership
                    affine types                        topology shapes
                                                        APIs

  **Merit           Explicit resource Compiler +        Strong targeted
  proposal**        relationships     selected          guarantees without
                                      mechanisms        one universal
                                                        topology
  ------------------------------------------------------------------------

### 1.2 Non-goals

-   Do not require a tracing garbage collector for ordinary safe code.
-   Do not pretend that all resource problems are equivalent to
    heap-memory reclamation.
-   Do not make arbitrary pointer manipulation silently safe.
-   Do not hide runtime ownership costs behind syntax that appears free.
-   Do not require a Rust-compatible borrow calculus merely for
    familiarity.
-   Do not prevent systems programming, C interoperability, intrusive
    structures, arenas, or custom allocators.

------------------------------------------------------------------------

## 2. Safety is not one property

"Memory safety" is too broad to serve as Merit's complete resource
contract.

A better decomposition is:

``` text
Safety =
    S_memory
  ∧ S_lifetime
  ∧ S_alias
  ∧ S_resource
  ∧ S_concurrency
  ∧ S_contract
```

  -----------------------------------------------------------------------
  Property                            Required meaning
  ----------------------------------- -----------------------------------
  `S_memory`                          No safe access outside a valid
                                      object/storage extent

  `S_lifetime`                        No safe access after the relevant
                                      lifetime has ended

  `S_alias`                           Mutation and aliasing obey the
                                      declared relationship

  `S_resource`                        Required acquisition/release
                                      behavior occurs deterministically

  `S_concurrency`                     Cross-thread access follows
                                      declared
                                      transfer/share/synchronization
                                      rules

  `S_contract`                        Bounds, shapes, preconditions,
                                      postconditions, and invariants hold
                                      as specified
  -----------------------------------------------------------------------

These properties may be enforced by different mechanisms.

That is intentional.

Rust strongly couples several of them through ownership and borrowing.
Managed runtimes couple several through managed references, runtime
metadata, bounds checks, and garbage collection.

Merit does not need to force every property through one mechanism.

------------------------------------------------------------------------

## 3. Design principles

### 3.1 Explicit authority

A type should communicate whether a value may:

-   destroy a resource,
-   transfer it,
-   mutate it,
-   share ownership,
-   or merely observe/access it.

### 3.2 Deterministic cleanup

Resources requiring timely release must not depend on eventual tracing
collection.

### 3.3 Pay for chosen semantics

`Owned<T>` and `Borrowed<T>` should not silently incur
reference-counting overhead.

If `Shared<T>` requires ownership accounting, that cost is justified by
the semantics explicitly requested.

### 3.4 Static where derivable

If invalidity follows from information available to the compiler, reject
it statically rather than inserting a runtime test.

### 3.5 Runtime where intrinsic

If correctness genuinely depends on dynamic information, use an explicit
runtime mechanism rather than pretending the compiler proved more than
it did.

### 3.6 Hazards are visible

Operations escaping ordinary guarantees require narrow,
capability-specific hazardous authority.

### 3.7 Interoperability is first-class

C ABI and foreign ownership rules must be expressible as actual
contracts rather than undocumented convention.

### 3.8 Stable semantics

Destruction order, moves, copies, layouts, resource failure, and
ownership transitions must be specified independently of optimizer
behavior.

------------------------------------------------------------------------

# 4. Core resource relationships

## 4.1 `Owned<T>`

`Owned<T>` represents exclusive destruction authority over a resource.

Conceptually:

``` text
owner ──────────> resource
                    │
                    └── exactly one destruction authority
```

### Proposed guarantees

An `Owned<T>` value:

-   has one active owner,
-   may be transferred,
-   is not implicitly duplicated,
-   deterministically releases its resource when ownership ends unless
    ownership has been transferred,
-   cannot be safely accessed through a borrow after destruction,
-   does not require reference counting merely because it is owned.

Conceptually:

``` text
a : Owned<T>

move a -> b

a = invalid as owner
b = current owner
```

### Proposed invariant

At any point:

``` text
destruction_authorities(T) <= 1
```

For a live owned resource:

``` text
destruction_authorities(T) = 1
```

unless authority has intentionally been transferred to a foreign system
or other explicitly modeled state.

------------------------------------------------------------------------

## 4.2 `Borrowed<T>`

`Borrowed<T>` represents access without destruction authority.

``` text
Owned<T>
    │
    ├──── Borrowed<T>
    ├──── Borrowed<T>
    └──── Borrowed<T>
```

A borrower does not keep the resource alive unless its type explicitly
says otherwise.

### Required invariant

``` text
lifetime(Borrowed<T>) ⊆ lifetime(resource)
```

A borrow therefore cannot safely outlive the resource from which it was
obtained.

### Important design question

Merit must decide whether borrowing itself encodes mutation exclusivity,
or whether lifetime authority and mutation authority are separate
concepts.

Rust approximately combines these through:

``` text
&T
&mut T
```

with the familiar rule:

``` text
many shared immutable references
OR
one exclusive mutable reference
```

Merit could adopt that rule, but it should do so only if the rule is
necessary for Merit's promised guarantees.

An alternative is to separate:

``` text
lifetime authority
mutation authority
thread authority
```

rather than treating them as one borrowing concept.

**Status: OPEN DESIGN DECISION.**

------------------------------------------------------------------------

## 4.3 `Shared<T>`

`Shared<T>` represents multiple ownership authorities.

Conceptually:

``` text
A ───┐
B ───┼────> T
C ───┘
```

The resource remains alive while at least one valid shared owner exists.

A straightforward implementation is reference counting:

``` text
owners(T) = N

destroy one Shared<T>:
    N := N - 1

if N == 0:
    destroy T
```

### Required semantic property

The language should specify the **ownership semantics**, not
unnecessarily mandate one implementation.

For example:

``` text
Shared<T> guarantees shared lifetime ownership.
```

A particular target/runtime may implement that using reference counting
when doing so preserves all specified observable semantics.

### Cost transparency

If copying a `Shared<T>` requires ownership accounting, this should be
documented as a non-zero operation.

The language should not imply:

``` text
Shared<T> copy == trivial pointer copy
```

when that is false.

------------------------------------------------------------------------

## 4.4 `Weak<T>`

`Weak<T>` observes a shared resource without keeping it alive.

``` text
Shared A ──────┐
Shared B ──────┼──> T
Weak C   ------┘
```

A weak reference must be promoted/validated before ordinary access.

Conceptually:

``` text
Weak<T>.acquire() -> Maybe<Shared<T>>
```

or equivalent.

Its primary purpose is to represent non-owning relationships in shared
graphs and break ownership cycles.

Example:

``` text
Parent
  |
  +-- Shared<Child>

Child
  |
  +-- Weak<Parent>
```

------------------------------------------------------------------------

# 5. Why `Shared` and `Weak` matter

Reference-counted ownership naturally fails on strong cycles:

``` text
A ─────> B
^        |
|        |
+--------+
```

If both edges maintain ownership:

``` text
count(A) >= 1
count(B) >= 1
```

even when the graph is otherwise unreachable.

Therefore Merit should not disguise cycles as a compiler accident.

The type system should make the distinction between:

``` text
ownership edge
```

and:

``` text
non-owning graph edge
```

visible.

`Weak<T>` provides one such mechanism.

Regions/arenas provide another.

Explicit graph ownership structures may provide others later.

------------------------------------------------------------------------

# 6. Regions and arenas

Many objects naturally share one lifetime.

Examples include:

-   compiler AST nodes,
-   parser structures,
-   HTTP request data,
-   game-frame temporary allocations,
-   temporary numerical workspaces,
-   query execution state,
-   transaction-local objects.

Instead of separately tracking:

``` text
A
B
C
D
E
F
```

they may belong to:

``` text
Arena R
├── A
├── B
├── C
├── D
├── E
└── F
```

and become invalid together:

``` text
destroy R
```

A possible future representation might resemble:

``` text
Region<R, T>
```

or an arena-owned allocation whose region identity is tracked
statically.

### Advantages

-   extremely cheap allocation is possible,
-   bulk reclamation is possible,
-   individual reference counts are unnecessary,
-   graph structures within one region become easier,
-   destruction/lifetime topology is simple.

### Restriction

Objects in a region naturally share the region's lifetime.

Therefore:

``` text
borrowed object from R
```

must not escape beyond:

``` text
lifetime(R)
```

unless ownership is explicitly transferred or copied elsewhere.

### Important complexity note

Bulk reclamation of raw storage can approach constant-time region
release, but resources with nontrivial destructors may still require
traversal or another cleanup strategy.

Merit must not promise:

``` text
destroy(region) == O(1)
```

for arbitrary resource-bearing contents unless the representation
actually guarantees it.

------------------------------------------------------------------------

# 7. Destruction semantics

Deterministic resource behavior requires deterministic destruction
rules.

Merit should specify at least:

1.  when scope-owned resources are destroyed,
2.  destruction ordering within a scope,
3.  destruction ordering of fields,
4.  behavior during error propagation,
5.  behavior during partial construction,
6.  whether destruction can fail,
7.  whether destructors may allocate,
8.  whether destructors may throw/propagate errors,
9.  interaction with process termination,
10. interaction with threads/tasks.

A desirable baseline is:

``` text
successful construction establishes ownership
ownership ending invokes deterministic cleanup
move transfers cleanup responsibility
borrow never acquires cleanup responsibility
```

For partial initialization:

``` text
construct A
construct B
construct C -> failure
```

the language must precisely define whether cleanup becomes:

``` text
destroy B
destroy A
```

and under what ordering rules.

**Status: REQUIRED SPECIFICATION WORK.**

------------------------------------------------------------------------

# 8. Aliasing and mutation

Memory lifetime and aliasing are separate problems.

Consider:

``` text
A ----\
       >---- T
B ----/
```

Even if both references are lifetime-valid, simultaneous mutation can
create:

-   data races,
-   iterator invalidation,
-   invariant violations,
-   optimization barriers,
-   surprising observable behavior.

Rust solves much of this by coupling mutation and borrowing.

Merit has several possible models.

## Model A --- Rust-like exclusivity

``` text
N read-only aliases
OR
1 mutable alias
```

### Benefits

-   strong static reasoning,
-   data-race prevention composes naturally,
-   optimizer gains alias information.

### Costs

-   ownership/alias topology leaks into APIs,
-   graphs and callbacks become harder,
-   programmers restructure otherwise-valid designs,
-   compiler lifetime analysis becomes substantially more complex.

## Model B --- ownership controls lifetime, separate rules control mutation

Example conceptual dimensions:

``` text
Owned<T>      = lifetime/destruction authority
Borrowed<T>   = lifetime access relationship
Mutable<T>    = mutation authority
Shared<T>     = shared lifetime ownership
ThreadSafe<T> = concurrency contract
```

### Benefits

-   orthogonal concepts,
-   potentially simpler mental model for many APIs,
-   Merit can enforce only the restrictions needed for each guarantee.

### Costs

-   more combinations of states,
-   type-system design becomes important,
-   unsafe aliasing must still be prevented where required.

## Model C --- runtime checked aliasing in selected structures

A type may explicitly request dynamic borrow checking or locking.

This resembles mechanisms such as Rust's `RefCell`, mutexes, or managed
synchronization.

### Principle

Runtime checks should be **opt-in through the selected type/mechanism**,
not silently introduced into ordinary borrowing.

**Recommended direction:** investigate Model B first, while retaining
Model A-like exclusivity where required to prove a specific safety
property.

------------------------------------------------------------------------

# 9. Concurrency

Thread safety should not be treated as an accidental consequence of
memory ownership.

Merit should explicitly answer:

``` text
Can this value move to another thread?
Can multiple threads access it?
Can multiple threads mutate it?
What synchronization mechanism protects it?
```

Potential concepts could include traits/capabilities analogous in
purpose---not necessarily syntax---to:

``` text
Transferable
Shareable
Synchronized
ThreadLocal
```

An owned resource might be movable between threads without becoming
shared:

``` text
Thread A:
    Owned<T>

transfer

Thread B:
    Owned<T>
```

This does not inherently require reference counting.

Shared cross-thread ownership may require stronger implementation
machinery:

``` text
Shared<T>
```

could require atomic accounting when crossing concurrency domains.

Merit should avoid charging atomic-reference-counting cost to values
that never request concurrent shared ownership.

------------------------------------------------------------------------

# 10. Arrays, slices, tensors, and views

This area is especially important for Merit.

A view into numerical storage is fundamentally a borrow.

Example:

``` text
Tensor<float>
      |
      +---- View<float>
```

The view may carry:

``` text
base storage identity
offset
shape
stride
element type
access authority
lifetime relationship
```

A safe view must satisfy bounds such as:

``` text
∀ accessed index i:
    address(i) ∈ valid_extent(base)
```

For multidimensional data:

``` text
address(i_0 ... i_n) =
    base + Σ(i_k * stride_k)
```

subject to:

``` text
0 <= i_k < shape_k
```

and overflow-safe address computation.

### Resource rule

A tensor view must not outlive its backing storage unless it
independently owns that storage.

This naturally distinguishes:

``` text
BorrowedView<T>
```

from a hypothetical independently owned tensor.

### Aliasing question

Overlapping mutable views require explicit semantics.

For example:

``` text
A = matrix[0..10, 0..10]
B = matrix[5..15, 5..15]
```

`A` and `B` overlap.

Merit must define whether:

-   simultaneous mutable views are statically rejected,
-   permitted but sequentially constrained,
-   dynamically checked,
-   explicitly hazardous,
-   or represented through a different type.

This is a major reason not to blindly import a general-purpose ownership
model before numerical semantics are finalized.

------------------------------------------------------------------------

# 11. FFI and foreign memory

C interoperability creates ownership states the compiler cannot infer
automatically.

Examples:

``` c
T* create();
void destroy(T*);
void borrow(T*);
void take_ownership(T*);
```

These APIs encode radically different contracts despite all using `T*`.

Merit's FFI declarations should be able to express those differences.

Conceptually:

``` text
foreign create() -> Owned<T>

foreign inspect(Borrowed<T>)

foreign consume(Owned<T>)

foreign observe(raw pointer)
```

The exact syntax is undecided.

### Foreign ownership questions

An FFI contract must be able to describe:

-   who allocates,
-   who deallocates,
-   which allocator must deallocate,
-   whether ownership transfers,
-   whether a pointer may be null,
-   whether storage may move,
-   callback lifetime,
-   thread affinity,
-   buffer length,
-   mutability,
-   alignment,
-   layout,
-   whether foreign code retains a reference.

------------------------------------------------------------------------

# 12. Hazardous capabilities

A single universal `unsafe` block is simple, but it erases useful
information.

Merit can potentially make hazardous authority more specific.

Examples:

``` text
hazard.raw_memory
hazard.foreign_pointer
hazard.unchecked_index
hazard.alias
hazard.layout
hazard.thread
hazard.lifetime
```

The exact names are not proposed syntax.

The principle is:

> A function should receive only the hazardous authority it actually
> requires.

This improves:

-   auditing,
-   code review,
-   static analysis,
-   documentation,
-   package security,
-   future sandboxing,
-   automated reasoning.

Instead of:

``` text
this function contains arbitrary unsafe behavior
```

Merit could communicate:

``` text
this function performs unchecked indexing
but cannot arbitrarily reinterpret memory
```

This is consistent with capability-oriented resource design.

------------------------------------------------------------------------

# 13. Raw memory

Systems programming still requires raw storage.

Examples include:

-   allocators,
-   kernels,
-   drivers,
-   SIMD buffers,
-   memory-mapped devices,
-   FFI,
-   serialization,
-   custom containers.

Raw storage should therefore exist, but should not automatically inherit
the guarantees of typed safe objects.

Conceptually:

``` text
RawMemory
    |
    +-- establish size
    +-- establish alignment
    +-- establish initialization
    +-- establish type/layout
    |
    v
TypedStorage<T>
```

Transitions from raw bytes to typed values require proof, checks, or
hazardous authority.

This keeps low-level programming possible without pretending arbitrary
bytes are automatically a valid `T`.

------------------------------------------------------------------------

# 14. Initialization state

A resource may exist before a valid `T` exists.

Therefore Merit should distinguish:

``` text
allocated storage
initialized value
moved-from value
destroyed storage
```

A conceptual state machine is:

``` text
unallocated
    |
    v
allocated / uninitialized
    |
    v
initialized / owned
    |
    +---- move ----> initialized / new owner
    |
    v
destroyed
    |
    v
deallocated
```

Not every resource follows every state, but the compiler/runtime model
must avoid treating them as interchangeable.

This matters particularly for:

-   arrays,
-   partial construction,
-   FFI output buffers,
-   placement construction,
-   custom allocators.

------------------------------------------------------------------------

# 15. Error handling and ownership

Error propagation must preserve resource invariants.

For:

``` text
A acquired
B acquired
C acquisition fails
```

Merit should guarantee deterministic cleanup of successfully acquired
resources unless ownership has already transferred.

A resource should never become leaked merely because control flow takes
an error path.

The language should define this independently of whether errors use:

-   result values,
-   propagation operators,
-   contracts,
-   exceptions,
-   or another mechanism.

------------------------------------------------------------------------

# 16. Resource contracts

A resource type should eventually be able to specify properties beyond
"has a destructor."

Examples:

``` text
must_close
thread_affine
noncopyable
movable
shared
pinned
foreign_owned
region_owned
```

These may ultimately be traits, capabilities, compiler-known properties,
or library abstractions.

The critical principle is that resource behavior should be
**machine-visible** rather than existing solely in documentation.

------------------------------------------------------------------------

# 17. Escape analysis

Compiler analysis may prove that some nominally heap-like objects do not
escape a scope.

For example:

``` text
create T
use T locally
return unrelated result
```

The compiler may be able to allocate `T` on the stack or inside a
temporary region.

This optimization must not change observable semantics.

Therefore:

``` text
semantic ownership != physical allocation strategy
```

`Owned<T>` should mean ownership authority, not necessarily
"malloc-backed pointer."

That distinction gives the optimizer freedom while keeping the language
model stable.

------------------------------------------------------------------------

# 18. Pinning and stable addresses

Some resources require an address not to change.

Examples:

-   self-referential foreign structures,
-   asynchronous OS operations,
-   DMA,
-   intrusive structures,
-   FFI callbacks,
-   certain device interfaces.

Merit should distinguish:

``` text
ownership
```

from:

``` text
address stability
```

A resource may be owned yet movable.

A pinned/stable resource adds another constraint.

Conceptually:

``` text
Owned<T> + StableAddress
```

should not be conflated with ownership itself.

**Status: FUTURE DESIGN AREA.**

------------------------------------------------------------------------

# 19. Graphs and intrusive structures

A useful stress test is a doubly linked structure:

``` text
A <----> B <----> C
```

A pure tree-oriented ownership model struggles because every node
naturally references neighbors.

Possible Merit representations include:

1.  one owning container + borrowed/internal node links,
2.  region ownership for all nodes,
3.  shared/weak edges,
4.  explicitly hazardous intrusive links,
5.  index/handle-based graphs.

Merit should support efficient graph structures without requiring
reference counting for every node.

This is a critical adversarial test for the design.

------------------------------------------------------------------------

# 20. Callbacks and closures

Callbacks create hidden lifetime relationships.

Example:

``` text
resource.register(callback)
```

Questions immediately arise:

``` text
Does resource retain callback?
What does callback capture?
Do captures remain alive?
Can callback outlive the registering scope?
Can it run on another thread?
```

The language must make retained versus non-retained callbacks
distinguishable.

Otherwise safe local borrowing can silently become an escaping lifetime.

------------------------------------------------------------------------

# 21. Proposed compile-time guarantees

Subject to final design, safe Merit should aim to reject or prevent:

  -----------------------------------------------------------------------
  Failure                             Desired default
  ----------------------------------- -----------------------------------
  Use-after-free                      Prevent

  Double destruction                  Prevent

  Access beyond allocation bounds     Prevent/check

  Borrow outliving owner              Prevent

  Implicit ownership duplication      Prevent

  Resource leak on ordinary error     Prevent
  propagation

  Wrong allocator/deallocator pair    Prevent where contract known

  Dereference of invalid weak         Require acquisition/check
  reference

  Shared strong-reference cycle       Not inherently preventable; make
                                      topology explicit

  Arbitrary foreign-pointer misuse    Hazardous boundary

  Data race                           Prevent where concurrency contract
                                      is statically known

  Integer overflow in address         Defined/checkable semantics
  calculation

  Uninitialized typed read            Prevent
  -----------------------------------------------------------------------

The specification should be precise about **prevent**, **runtime
check**, **hazardous operation**, and **not guaranteed**.

Those are different promises.

------------------------------------------------------------------------

# 22. Proposed runtime costs

A core Merit principle should be:

> **The selected abstraction determines the cost.**

  -----------------------------------------------------------------------
  Relationship                        Expected ordinary runtime machinery
  ----------------------------------- -----------------------------------
  `Owned<T>`                          None beyond normal
                                      construction/destruction

  `Borrowed<T>`                       Ideally none for lifetime tracking

  `Shared<T>`                         Ownership accounting as required

  `Weak<T>`                           Shared-control metadata / validity
                                      acquisition

  Region/Arena                        Region allocator + bulk lifetime
                                      management

  Checked indexing                    Bounds check unless statically
                                      eliminated

  Hazardous raw access                No automatic safety check unless
                                      explicitly requested

  Cross-thread shared ownership       Potential atomic/synchronization
                                      cost
  -----------------------------------------------------------------------

This makes performance consequences understandable from source-level
semantics.

------------------------------------------------------------------------

# 23. Comparison with Rust

Rust demonstrates that substantial memory and concurrency safety can be
obtained without a tracing garbage collector.

Merit should preserve that achievement while questioning which
restrictions are actually necessary for Merit's goals.

## Rust approach

Roughly:

``` text
ownership
    +
borrowing
    +
lifetime analysis
    +
alias/mutation exclusivity
    +
Send/Sync-style concurrency properties
    |
    v
strong static guarantees
```

### Benefits

-   no mandatory GC,
-   deterministic destruction,
-   strong use-after-free prevention,
-   strong data-race prevention,
-   powerful optimizer information,
-   low runtime lifetime overhead.

### Side effects

-   lifetime topology becomes part of API architecture,
-   graphs and self-reference require specialized patterns,
-   programmers sometimes restructure valid algorithms to satisfy the
    model,
-   compiler/type-system complexity is high,
-   concepts such as `Rc`, `Arc`, `Weak`, `RefCell`, `Mutex`, `Pin`, and
    `unsafe` emerge for ownership relationships outside the simplest
    tree model.

## Merit opportunity

Merit can ask a narrower question:

> **What is the minimum explicit information required to prove each
> guarantee Merit actually promises?**

Rather than:

> **Can every safe program be represented through one universal
> borrowing discipline?**

------------------------------------------------------------------------

# 24. Comparison with managed runtimes

Managed languages solve a different problem by retaining runtime
knowledge about object reachability.

Conceptually:

``` text
roots
  |
  +---- A ---- B
  |
  +---- C

reachable = alive
unreachable = reclaimable
```

This largely eliminates explicit memory deallocation.

However, garbage collection answers:

``` text
When is memory unreachable?
```

It does not necessarily answer:

``` text
When must this external resource be released?
```

Therefore managed languages still require deterministic resource
patterns for:

-   files,
-   sockets,
-   locks,
-   transactions,
-   native handles,
-   GPU resources.

Merit's resource model should treat this distinction as fundamental.

------------------------------------------------------------------------

# 25. Comparison with C and C++

C effectively permits the programmer to assert lifetime correctness
manually.

C++ adds powerful mechanisms including:

-   RAII,
-   deterministic destructors,
-   move semantics,
-   smart pointers,
-   containers,
-   static analysis,
-   sanitizers.

But unsafe ownership states remain representable.

Merit should retain the important systems advantages:

``` text
explicit layout
C interoperability
deterministic cleanup
custom allocation
low-level access
predictable cost
```

while making common invalid resource relationships unrepresentable or
explicitly hazardous.

------------------------------------------------------------------------

# 26. Self-hosting implications

Self-hosting makes these decisions more urgent because the Merit
compiler itself will become a large consumer of the resource model.

A compiler naturally contains:

-   ASTs,
-   token streams,
-   source buffers,
-   symbol tables,
-   graphs,
-   scopes,
-   diagnostics,
-   IR,
-   temporary numerical/storage structures,
-   caches,
-   foreign/system resources.

This is an excellent validation environment.

### Likely compiler allocation topology

A Merit compiler could naturally use:

``` text
long-lived compiler/session ownership
        |
        +-- source/module regions
        |
        +-- AST arenas
        |
        +-- symbol/type ownership
        |
        +-- temporary pass regions
        |
        +-- explicitly shared immutable structures
```

This suggests that **regions/arenas should be evaluated early**, even if
their final public syntax comes later.

Self-hosting should exercise the resource model, not accidentally freeze
a weak one.

------------------------------------------------------------------------

# 27. Adversarial test suite for the design

Before declaring the model stable, Merit should be able to explain these
cases precisely.

## 27.1 Simple ownership

``` text
create A
move A to B
use old A
```

Expected: compile-time rejection of old-owner use.

## 27.2 Borrow escape

``` text
owner exists in inner scope
borrow returned to outer scope
owner destroyed
borrow used
```

Expected: compile-time rejection.

## 27.3 Shared cycle

``` text
A strongly owns B
B strongly owns A
external owners disappear
```

Expected: semantics explicitly identify possible cycle retention unless
a weak/region strategy is used.

## 27.4 Parent/child graph

``` text
Parent owns Child
Child references Parent
```

Expected: efficient representation without unnecessary global sharing.

## 27.5 Doubly linked list

``` text
A <-> B <-> C
```

Expected: no forced per-node atomic reference counting.

## 27.6 Tensor slices

``` text
base tensor
two overlapping mutable views
```

Expected: exact alias/mutation rule.

## 27.7 FFI ownership transfer

``` text
Merit allocates T
C library takes ownership
Merit attempts destruction
```

Expected: double destruction impossible through safe declared FFI
contract.

## 27.8 Callback retention

``` text
local value borrowed by callback
foreign system retains callback
local scope ends
callback executes
```

Expected: escape recognized or operation requires explicit
hazardous/owned capture semantics.

## 27.9 Thread transfer

``` text
Thread A owns T
ownership transferred to Thread B
Thread A attempts access
```

Expected: old access rejected.

## 27.10 Partial construction

``` text
field A constructed
field B constructed
field C fails
```

Expected: deterministic cleanup specified.

## 27.11 Arena escape

``` text
object allocated in arena R
reference returned beyond R
R destroyed
reference used
```

Expected: rejected unless storage is explicitly promoted/transferred.

## 27.12 Self-reference

``` text
object contains pointer/view into itself
object moves
```

Expected: either address-stability requirement, safe representation, or
explicit hazardous boundary.

------------------------------------------------------------------------

# 28. Proposed conceptual model

A useful way to think about the initial system is:

``` text
                         RESOURCE

                            |
          +-----------------+-----------------+
          |                 |                 |
       Owned<T>          Shared<T>         Region-owned
          |                 |                 |
          |                 +---- Weak<T>     |
          |                                   |
          +---- Borrowed<T> <-----------------+
```

Orthogonal properties may then describe:

``` text
mutation authority
thread transfer
thread sharing
address stability
layout
foreign ownership
bounds/shape
hazardous capabilities
```

This avoids forcing every concern into `Owned` versus `Borrowed`.

------------------------------------------------------------------------

# 29. Proposed normative direction

The following is a reasonable initial target for Merit.

### MUST

-   Ownership transfer must be explicit in semantics.
-   Safe code must not double-destroy an owned resource.
-   Safe borrows must not outlive their backing resource.
-   Destruction must be deterministic for deterministic resources.
-   Error propagation must preserve ownership/cleanup invariants.
-   FFI must be able to declare ownership transfer.
-   Raw memory operations outside proven-safe abstractions must require
    hazardous authority.
-   Runtime costs associated with sharing must not silently infect
    exclusive ownership.
-   Array/tensor/view bounds and backing-storage lifetime must have
    defined semantics.

### SHOULD

-   Keep lifetime ownership separate from physical allocation strategy.
-   Keep address stability separate from ownership.
-   Investigate mutation authority as orthogonal to lifetime borrowing.
-   Support regions/arenas as a first-class or compiler-recognizable
    lifetime topology.
-   Permit graph structures without requiring universal reference
    counting.
-   Make hazardous capabilities narrower than one unrestricted `unsafe`
    authority where practical.
-   Make concurrency authority explicit rather than incidental.

### MAY

-   Use reference counting to implement `Shared<T>`.
-   Use escape analysis to stack-allocate owned values.
-   Eliminate bounds checks when statically proven.
-   Specialize shared ownership when whole-program analysis proves
    uniqueness.
-   Provide dynamically checked aliasing abstractions as opt-in
    library/runtime types.

------------------------------------------------------------------------

# 30. Open design decisions

These questions should be resolved deliberately rather than inherited
from another language.

  -----------------------------------------------------------------------
  Question                            Why it matters
  ----------------------------------- -----------------------------------
  Does `Borrowed<T>` imply read-only  Determines whether lifetime and
  access?                             mutation authority are coupled

  What represents exclusive mutable   Central to alias safety and
  access?                             optimization

  Are lifetimes inferred, named,      Determines syntax and compiler
  scoped, or structural?              complexity

  Is `Shared<T>` specified as RC or   Determines ABI and implementation
  abstract shared ownership?          freedom

  How are cycles diagnosed?           Affects usability of shared graphs

  Are regions first-class types?      Important for compiler, games,
                                      parsing, numerical workloads

  Can destructors fail?               Changes error and unwinding
                                      semantics

  What is destruction order?          Required for determinism

  What happens during panic/fatal     Defines resource guarantees under
  termination?                        abnormal control flow

  How are callbacks' retained         Critical for FFI and async systems
  lifetimes represented?

  How is pinning/address stability    Needed for some FFI and intrusive
  represented?                        structures

  How are overlapping tensor views    Central to numerical performance
  handled?                            and safety

  Which hazardous capabilities exist? Determines auditability and
                                      low-level expressiveness

  What concurrency                    Determines static data-race
  traits/capabilities exist?          guarantees
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 31. Design litmus test

For every proposed feature, ask:

``` text
1. What invalid program are we preventing?

2. Can the compiler prove that invalidity?

3. If not, can an explicit runtime mechanism check it?

4. What runtime cost does that mechanism impose?

5. Can the programmer choose a different resource topology
   when that cost is inappropriate?

6. If neither static proof nor runtime enforcement is practical,
   what narrow hazardous capability expresses the remaining authority?

7. Are the observable semantics deterministic?
```

This prevents "safety" from becoming an undefined justification for
arbitrary restrictions.

------------------------------------------------------------------------

# 32. The intended Merit position

The major historical strategies can be summarized as:

``` text
C:
    "Trust the programmer."

C++:
    "Use deterministic abstractions, but retain escape routes."

Java / C#:
    "Let the managed runtime control memory lifetime."

Rust:
    "Express ownership so the compiler can prove lifetime and alias rules."

Merit:
    "Declare the resource relationship;
     let the compiler enforce what follows from it;
     pay runtime cost only where that relationship requires it;
     make remaining hazards explicit."
```

The goal is not fewer rules at any cost.

The goal is **the smallest set of rules that directly correspond to
Merit's promised guarantees**.

That gives Merit a coherent place in the language-design space:

> **Deterministic resource safety without mandatory garbage collection,
> without unmanaged-by-default lifetime semantics, and without requiring
> all safe program architecture to conform to a single ownership
> topology.**

------------------------------------------------------------------------

# 33. Recommended implementation sequence

For the self-hosting transition, the safest order is:

1.  **Freeze the semantic meaning of `Owned<T>` and moves.**
2.  **Define deterministic destruction and partial-construction
    cleanup.**
3.  **Define `Borrowed<T>` lifetime validity.**
4.  **Separate or deliberately couple mutation authority.**
5.  **Specify `Shared<T>` / `Weak<T>` semantics.**
6.  **Prototype arena/region use inside the compiler.**
7.  **Specify FFI ownership annotations and hazardous capabilities.**
8.  **Apply the model to arrays, slices, tensor views, and overlapping
    storage.**
9.  **Specify thread transfer/sharing semantics.**
10. **Build the adversarial resource-model test suite.**
11. **Only then treat the resource model as sufficiently stable for
    broad self-hosted compiler architecture.**

This does not require every future feature to be implemented before
self-hosting.

It does require that the self-hosted compiler not accidentally establish
ownership assumptions Merit later has to fight.

------------------------------------------------------------------------

## Appendix A --- Core invariants

### Exclusive ownership

``` text
live_owned_resource(T)
    => destruction_authorities(T) = 1
```

### Borrow validity

``` text
lifetime(Borrowed<T>)
    ⊆ lifetime(backing_resource)
```

### Move

``` text
move(A -> B)
    => owner(A) becomes invalid
    && owner(B) becomes authoritative
```

### Shared ownership

``` text
resource_alive(T)
    while strong_owners(T) > 0
```

### Weak ownership

``` text
Weak<T>
    does not increment strong_owners(T)
```

### Region membership

``` text
lifetime(member)
    ⊆ lifetime(region)
```

unless ownership/storage is explicitly transferred.

### View validity

``` text
lifetime(view)
    ⊆ lifetime(backing_storage)
```

and:

``` text
∀ access i:
    computed_address(i) ∈ backing_storage_extent
```

------------------------------------------------------------------------

## Appendix B --- Terminology

**Owner**\
An entity with authority/responsibility for ending a resource's
lifetime.

**Borrower**\
An entity with temporary access but no destruction authority.

**Shared owner**\
One of multiple entities whose ownership relationship keeps a resource
alive.

**Weak reference**\
A non-owning reference to shared state that must establish current
validity before access.

**Region / arena**\
A lifetime domain in which multiple allocations/resources are grouped
under a common lifetime.

**Move**\
Transfer of ownership authority without semantically duplicating the
resource.

**Resource**\
Anything whose acquisition, validity, use, or release is governed by a
lifetime contract; not limited to memory.

**Hazardous operation**\
An operation for which ordinary Merit safety guarantees cannot be
established and which therefore requires explicit additional authority.

**Physical allocation strategy**\
Where/how storage is actually allocated. This is distinct from semantic
ownership.

**Address stability**\
A guarantee that an object's storage address will not change for a
specified lifetime.

------------------------------------------------------------------------

*End of Draft 0.1*
