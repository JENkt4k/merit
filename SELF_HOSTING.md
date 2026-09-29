# Merit Self-Hosting Ledger

## Objective

Make the trusted Merit replacement compiler reproducibly compile its complete
source through the normal public project interface. The resulting artifact must
be immediately usable as the compiler for the next stage. Python remains an
independent semantic and diagnostic oracle and may orchestrate processes, files,
and the external C toolchain, but it must not parse Merit, rewrite source
semantics, materialize compiler MIR, select backend meaning, or emit production
C for the self-hosted path.

This campaign begins from `main` commit
`a2a9f31dd3e1e2fee04c8ba3f557775a6582b841`, after the bounded post-Alpha.2
cleanup closed. SH0 merged as PR #128 at `34f8cc7`. This campaign does not authorize Alpha.3 language features.

## Definitions

- **Reference compiler**: the Python implementation used as an independent
  semantic and diagnostic oracle.
- **Trusted replacement compiler**: the Alpha.2 Merit-native semantic frontend
  plus the established production replacement path.
- **Self-hosted compiler**: a trusted compiler artifact that, through the
  normal project interface, reproducibly compiles the complete compiler project
  into the next usable compiler artifact.
- **Stage 0**: the trusted seed compiler produced by the independent reference
  path.
- **Stage 1**: the complete compiler project built through the normal project
  interface using stage 0.
- **Stage 2**: the same compiler project, from a fresh isolated source tree,
  built through the same interface using stage 1.
- **Normal project interface**: the public `merit-project build` command acting
  on a standard `Merit.toml`. Callers may select a compiler artifact explicitly,
  but may not import private Python bootstrap modules or invoke a separate
  bootstrap-only build API.
- **Semantic work**: source interpretation, desugaring, name/type resolution,
  ownership, contracts, capabilities, MIR construction/materialization,
  diagnostic selection, and deterministic C/header emission.
- **Permitted host work**: argument parsing, manifest/file transport, process
  launch, atomic publication, hashing, invoking the system C compiler/linker,
  and comparing already-produced artifacts. Host work must not alter program
  meaning.

Self-hosting is an implementation provenance claim, not independent correctness
evidence. The Python oracle, accepted/rejected corpus, interpreter/native parity,
acceptance projects, and reproducibility gates remain required.

## Normal project UX contract

The ordinary installed-tool workflow is:

```text
merit-project build compiler \
  -o build/merit-replacement-frontend
```

The explicit stage workflow is:

```text
merit-project build compiler \
  --compiler-path .merit/stages/stage-0/merit-replacement-frontend \
  -o .merit/stages/stage-1/merit-replacement-frontend

merit-project build compiler \
  --compiler-path .merit/stages/stage-1/merit-replacement-frontend \
  -o .merit/stages/stage-2/merit-replacement-frontend
```

`--compiler-path` is the intended public spelling for explicit compiler
selection. The current `--replacement-driver` spelling may remain as a
short-lived compatibility alias only if a reviewed migration requires it. The
default command discovers an installed trusted compiler; it must never silently
fall back to Python semantic compilation.

The output is one directly executable replacement compiler implementing the
versioned compiler protocol. It is not merely a test program, shared library,
snapshot directory, or artifact requiring a private relinking step.

Compiler selection order is deterministic:

1. explicit `--compiler-path`;
2. reviewed project/toolchain configuration, if introduced;
3. `merit-replacement-frontend` on `PATH`;
4. fail closed with a structured diagnostic.

Environment variables may support automation but are not the primary documented
user interface. Compiler-specific meaning belongs in Merit source and its
versioned protocol, not in a privileged manifest kind.

## Complete Merit source inventory

The canonical compiler project is `compiler/Merit.toml`. Its ordinary source
glob references the same complete 46-module source closure under
`examples/projects/bootstrap_lexer/src`. The executable contract names the
exported `emit_replacement_bundle(String)` function in
`src/native_replacement_driver.mrt`. The historical bootstrap manifest remains
the corpus/probe project; it is not the documented compiler target.

| Domain | Merit source modules | Current conclusion |
|---|---|---|
| Lexing, syntax, statements, and expressions | `tokens.mrt`, `lexer.mrt`, `syntax.mrt`, `clauses.mrt`, `statements.mrt`, `statement_structure.mrt`, `statement_semantics.mrt`, `expression_spans.mrt`, `expression_validity.mrt` | Expressible in Merit; included in stage builds |
| HIR | `hir.mrt`, `hir_generics.mrt`, `hir_strings.mrt` | Expressible in Merit; included in stage builds |
| MIR core and composites | `mir.mrt`, `mir_composite.mrt`, `mir_functions.mrt`, `mir_generics.mrt`, `mir_cfg.mrt`, `mir_cfg_placement.mrt` | Expressible in Merit; included in stage builds |
| Function discovery, contracts, metadata, and assembly | `mir_source_function_records.mrt`, `mir_source_function_record_stats.mrt`, `mir_source_function_pipeline.mrt`, `mir_function_contracts.mrt`, `mir_function_clause_metadata.mrt`, `mir_function_instruction_source.mrt`, `mir_function_assembly_plan.mrt`, `mir_function_assembly.mrt`, `mir_resolved_source_function_pipeline.mrt`, `mir_resolved_source_function_assembly.mrt`, `mir_resolved_source_function_snapshot.mrt`, `mir_resolved_source_function_bundle.mrt` | Expressible in Merit; included in stage builds |
| Ownership, lifecycle, control flow, and placement | `mir_ownership_flow.mrt`, `mir_source_ownership_metadata.mrt`, `mir_source_ownership_expression.mrt`, `mir_source_ownership_control.mrt`, `mir_source_ownership_lowering.mrt`, `mir_source_type_lifecycle.mrt`, `mir_statement_lowering.mrt`, `mir_structured_lowering.mrt`, `mir_match_capability_flow.mrt`, `mir_resolved_control_flow.mrt`, `mir_function_ownership_assembly.mrt` | Expressible in Merit; included in stage builds |
| Generics and project types | `mir_generic_catalog.mrt`, `mir_generic_expansion.mrt`, `mir_project_payload_types.mrt` | Expressible in Merit; included in stage builds |
| Native compiler protocol entry | `native_replacement_driver.mrt` | Merit-native semantic entry is exposed through the ordinary `stdin-string-i32` executable adapter |
| Versioned project request | `project_request.mrt` | Merit-native framing validation, module/import canonicalization, capability deduplication, newline normalization, and legacy Alpha.1 vector desugaring |

This list is the required compiler semantic-source closure for the initial
self-hosting campaign. Moving or renaming it is not required. Any newly
discovered required semantic implementation outside this closure must be added
to the inventory before it is migrated.

## Current special-stage seam audit

The present M9 path proves stage agreement, but `build_replacement_compiler_stage`
is a privileged Python assembly path rather than the normal project UX.

| Seam | Current owner and behavior | Classification | Required disposition |
|---|---|---|---|
| Manifest parsing and file discovery | `merit/project/manifest.py` reads TOML and paths | Permitted host work | May remain host-side if it passes bytes and metadata without semantic interpretation |
| Module/import discovery | `project_request.mrt` discovers module/import syntax after the host transports path-sorted bytes | Merit-native source interpretation | Closed in SH2; the host loader no longer defines Merit grammar |
| Multi-module source envelope | `project_request.mrt` validates and canonicalizes the versioned `MPRQ` request; the former Python `replacement_source.py` seam is removed | Merit-native source canonicalization | Closed in SH2 with single/multi-module, CRLF, qualification, duplicate-capability, and legacy-vector evidence |
| Capability labels | Bundle v3 carries module and capability names emitted from the native catalogs | Merit-native semantic metadata | Closed in SH2; Python publishes native metadata without source scanning |
| Driver execution | `replacement_prepare.py` launches one executable with bounded input/output and timeout | Permitted host work | Retain as generic protocol transport, with structured request/response framing |
| Bundle framing validation | `resolved_source_function_bundle.py` validates the versioned integer transport | Representation adapter | May remain for oracle/testing; production self-hosted build must not depend on Python to create the next compiler artifact |
| Snapshot decoding | `resolved_source_function_snapshot.py` decodes native records | Representation adapter | Python copy remains oracle evidence; production decoding/materialization moves behind the compiler artifact |
| Canonical MIR materialization | `resolved_source_function_snapshot.py` and `replacement_project.py` construct Python `MirModule` data from native records | Compiler/backend work | Must migrate out of the production self-hosted path |
| MIR contract implementation | `merit/bootstrap/mir_contract.py` defines Python canonical MIR objects and validation | Oracle plus current production adapter | Retain as independent oracle; next-stage production must consume Merit-owned canonical MIR |
| Deterministic C/header emission | `merit/bootstrap/mir_to_c.py` emits production C and headers | Backend semantic work | Must migrate behind the Merit compiler executable with byte-stable comparison evidence |
| C compilation and linking | `replacement_build.py` invokes the external C11 compiler/linker | Permitted host/toolchain work | May remain generic and non-semantic; commands and failures must be deterministic and recorded |
| Compiler process host | `merit/project/executable_adapter.py` provides the manifest-selected, generic `stdin-string-i32` process/ABI adapter; `native_frontend_driver.py` delegates to it | Permitted generic runtime/ABI bridge | Closed for SH1; keep semantic interpretation out of the adapter |
| Shared-library construction | The ordinary reference and replacement project builders construct the adapter's library; the historical stage helper still calls `build_replacement_shared` | Bootstrap-only stage path remains | Eliminate the remaining private stage helper during SH4; public project build already produces a usable executable |
| Source isolation | `native_frontend_driver.py` copies the compiler project while excluding `.merit`, build, and bytecode state | Trust orchestration | Retain and generalize in the reproducibility gate |
| Stage comparison | `reproducibility.py` builds stages and compares C, header, and fixed probe output | Trust orchestration | Retain, then extend to invoke only the public project command and the self-hosting result schema |
| CLI compiler discovery | `merit/project/cli.py` selects argument, environment, or `PATH` driver | Public UX with historical naming | Introduce `--compiler-path`, preserve deterministic discovery, and fail closed |

The external C compiler, platform linker, filesystem, and process launcher are
not required to be written in Merit. They are toolchain dependencies and may
remain host-provided so long as they do not interpret or alter Merit semantics.

## Required source-expressibility audit

Before an implementation milestone may claim closure, its PR must update this
table with direct evidence. “Compiles” alone is insufficient: every dependency
needed to produce the next usable compiler must be classified.

| Requirement | Current state | Closure evidence |
|---|---|---|
| All 46 Merit modules are present in the manifest source closure | Proven by manifest glob and M9 isolated stage builds; SH2 adds the reviewed project-request module | Automated exact-inventory test rejects accidental omission/addition until deliberately reviewed |
| Compiler semantic entry is Merit-native | `emit_replacement_bundle(String)` is Merit source | Direct interpreter/native and prior-stage execution parity |
| Compiler artifact has an ordinary executable entry | `compiler/Merit.toml` declares `stdin-string-i32` and `emit_replacement_bundle`; ordinary project build links the fixed generic adapter | Public project-build and native-driver tests produce and execute the compiler without bespoke host generation |
| Project/module request is representable without Python source rewriting | Closed in SH2 by `MPRQ` v1 and native bundle metadata v3 | Host framing oracle, malformed-request rejection, Windows binary transport, single/multi-module execution parity, and legacy Alpha.1 vector evidence |
| Complete canonical MIR is materialized by Merit | Missing in the production path | Native MIR artifact comparison against the independent Python materializer |
| Deterministic C and public header are emitted by Merit | Missing | Byte comparison with the established canonical emitter over the complete accepted corpus and compiler project |
| Diagnostics and failures are represented without Python semantic guessing | Partial; Python currently infers source hints from wrapped statuses | Structured native diagnostics compared with the oracle contract |
| Required filesystem/process authority is explicit | Not yet applicable to the compiler executable boundary | Capability inventory and negative tests for missing authority |
| The resulting artifact can compile the same complete source closure | Proven only through the private M9 stage helper | Stage 1 and stage 2 built solely by the public command |
| Python is absent from production semantic authority | True for frontend lowering, false for materialization/backend | Import/process guard proves the stage build cannot reach prohibited Python semantic modules |

## Scope rules

- Preserve the tagged Alpha.2 language surface, accepted/rejected behavior,
  serialization, ABI, ownership, diagnostics, and interpreter/native parity.
- Do not add stored references, lifetime parameters, allocator-aware views,
  tensors, new generic features, or other Alpha.3 semantics.
- Do not introduce a second compiler pipeline. Migrate the established canonical
  boundaries vertically and delete or demote replaced production seams.
- Do not call transport-only code “self-hosted” while Python still materializes
  compiler MIR or emits production C.
- Do not require native executable or shared-library byte identity; platform
  toolchains control non-canonical metadata. Canonical Merit-generated C,
  headers, protocol artifacts, and diagnostics follow explicit comparison rules.
- Do not remove the Python oracle. Production authority and independent
  comparison evidence must remain distinct.
- Do not make the compiler project a privileged manifest kind merely to hide the
  current C host. Prefer ordinary executable/runtime facilities usable by other
  Merit projects.
- Do not broaden package management, separate compilation, incremental builds,
  or dependency-granular caching into this campaign.

## Ordered milestones

- [x] **SH0 — Inventory and contract**: merged as PR #128; locked the exact
  45-module source closure, public command, allowed host boundary, prohibited
  semantic seams, stage identities, and evidence requirements. No compiler code.
- [x] **SH1 — Ordinary compiler executable**: make the compiler project produce
  the versioned native compiler protocol as an ordinary executable artifact.
  Remove stage-builder ownership of the bespoke generated C host. Preserve the
  existing protocol and all frontend semantic evidence.
- [x] **SH2 — Native project request**: replace Python regex discovery,
  source flattening/desugaring, capability labeling, and diagnostic guessing
  with a versioned project request consumed and validated by the Merit compiler.
  Preserve multi-module source identity and fail closed on malformed requests.
- [ ] **SH3 — Merit-owned canonical MIR and backend**: move production snapshot
  decoding/materialization, canonical project MIR assembly, deterministic C
  emission, and public-header emission behind the Merit compiler executable.
  Keep Python implementations as independent comparison oracles.
- [ ] **SH4 — Normal build cutover**: make the documented
  `merit-project build ... --compiler-path ...` command produce a directly usable
  next-stage compiler. Remove the private stage-build API from production use and
  add a guard against Python semantic/backend imports during the build.
- [ ] **SH5 — Self-hosted stage equivalence**: build isolated stages 1 and 2 only
  through the public command. Prove canonical artifact, protocol, diagnostics,
  corpus, acceptance-project, and runtime agreement under a versioned
  machine-readable self-hosting report.
- [ ] **SH6 — Cross-platform qualification and handoff**: pass focused,
  subsystem, full, corpus, replacement-acceptance, and self-hosting gates on the
  required local and hosted Ubuntu/native-Windows environments; update status,
  architecture, manual/tooling documentation, limitations, and release evidence.

One PR should close one coherent milestone unless the active ledger records a
specific dependency or reviewability reason to split it. Never begin a successor
milestone before its prerequisite is confirmed merged on current `main`.

### SH0 candidate evidence

- The filesystem and ledger inventories match exactly: 45 `.mrt` source paths,
  with no missing or extra compiler module. The manifest source contract remains
  `src/**/*.mrt`.
- The special-stage audit traces the public CLI, replacement loader and project
  envelope, artifact preparation, bundle/snapshot decoding, canonical MIR
  materialization, C/header emission, native host construction, external
  compilation/linking, isolation, and stage comparison.
- `tests/test_release_docs.py` locks the complete source inventory, active-plan
  references, public UX, SH0-SH6 milestone bounds, machine-readable evidence,
  cross-platform requirement, and Alpha.3 exclusion (`10 passed`).
- The canonical native-Windows fast gate passes (`92 passed`).
- This milestone changes planning, status, architecture, specification, and
  documentation tests only. It changes no compiler, runtime, serialization,
  ABI, or language behavior.

### SH1 candidate evidence

- `compiler/Merit.toml` is the canonical ordinary compiler target and resolves
  the exact 45-module source closure while selecting the Merit-native
  `emit_replacement_bundle(String) -> i32` entry.
- `[executable] adapter = "stdin-string-i32"` is a general manifest contract;
  both reference and replacement project builds use the same fixed transport
  adapter, which reads bytes, constructs the stable `String` ABI value, invokes
  one exported Merit function, and returns its status without inspecting source.
- `native_frontend_driver.py` no longer owns a bespoke generated C host or C
  compiler invocation. Stage 0 uses the ordinary compiler manifest and project
  build, while the historical stage helper delegates final linking to the same
  generic adapter pending SH4 removal of that private stage path.
- The public spelling is `--compiler-path`; `--replacement-driver` remains a
  compatibility alias. Compiler discovery remains deterministic and fail-closed.
- The existing versioned stdout protocol and `replacement driver status N`
  diagnostic remain unchanged. No language, serialization, or ABI surface is
  broadened.
- A black-box `merit-project build compiler --compiler reference -o <path>`
  smoke test produces a directly executable compiler, and a valid Merit source
  probe emits the established versioned replacement bundle through stdout.

### SH3 implementation audit

SH3 moves one vertical production boundary. It is not satisfied by wrapping
the existing Python backend or by adding another host-side snapshot adapter.
The current authorities and required final dispositions are:

| Current production authority | Audited surface | SH3 disposition |
|---|---:|---|
| `resolved_source_function_snapshot.py` | 634 lines; snapshot decoding, type reconstruction, canonical MIR materialization | Retain only as an independent oracle; normal builds consume a Merit-produced canonical artifact without calling its decoder/materializer |
| `replacement_project.py` | 173 lines; cross-function assembly, destructor merging, payloadless-enum normalization, call-target validation | Move project assembly and normalization into Merit; retain Python assembly only for differential evidence |
| `mir_to_c.py` | 1,777 lines; 43 definitions covering types, runtime support, instructions, terminators, functions, destructors, C module, and public header | Implement the established deterministic emission contract in Merit and compare C/header bytes against this independent oracle |
| `replacement_build.py` | 159 lines; current semantic artifact handoff plus permitted C compiler/linker launch | Remove semantic materialization/emission from the production call path; retain only generic artifact publication and external toolchain invocation |
| `project/replacement.py` | Production reader currently imports the Python snapshot decoder, project assembler, and backend transitively | Cut over to versioned native C/header artifacts, validate framing/digests, publish atomically, then invoke only the generic C toolchain bridge |

The target response extends the existing versioned native compiler protocol;
it carries canonical MIR identity plus complete deterministic C and public-header
bytes. Host Python may validate lengths, hashes, paths, and UTF-8 framing, but
must not reconstruct MIR, choose C representations, patch emitted C, or derive
header exports. Historical snapshot/bundle versions remain readable only by
oracle and compatibility tests, not by the final SH3 production build path.

## Per-PR evidence

Every implementation PR must record:

1. the exact compiler-source and host seams changed;
2. before/after production authority for each seam;
3. accepted and rejected cases, including fail-closed behavior;
4. Python-oracle differential evidence where a semantic/backend seam moves;
5. interpreter/native behavior and deterministic artifact evidence;
6. proof that no language, serialization, ABI, or diagnostic contract changed;
7. focused tests, then the affected subsystem gate;
8. a full gate only when the candidate is complete;
9. hosted evidence required by that milestone;
10. explicit confirmation that the next-stage artifact was produced through the
    public command rather than a private bootstrap API.

## Self-hosting comparison contract

Stage 1 and stage 2 must use fresh isolated compiler source trees and empty
project-local build/cache state. The following are canonical and byte-identical:

- generated Merit C for the compiler project;
- generated public compiler header;
- versioned compiler protocol output for the fixed probe corpus;
- versioned structured diagnostics for the fixed rejected probe corpus;
- source-closure manifest and canonical source digests;
- any serialized canonical MIR or bundle retained by the final interface.

The stage-0, stage-1, and stage-2 compilers must all:

- execute successfully;
- accept the same accepted corpus and reject the same rejected corpus;
- produce equivalent acceptance-project behavior;
- fail closed rather than invoke Python semantic fallback;
- report their compiler identity, protocol version, source-closure digest, and
  canonical artifact hashes in the self-hosting result.

Native object files, libraries, and executables must execute correctly but need
not be byte-identical across stages or platforms.

## Machine-readable evidence

The final gate is named `self-hosting`:

```text
python scripts/gate.py self-hosting
```

It writes `.merit/gates/self-hosting/result.json` with a versioned schema and a
terminal `MERIT_SELF_HOSTING_RESULT=PASS|FAIL` marker. At minimum the report
contains:

- repository commit and dirty-tree state;
- platform and external C toolchain identity;
- compiler source-closure paths and digest;
- stage producer identity and protocol version;
- public command executed for each stage;
- confirmation of fresh isolated source/build/cache roots;
- canonical C/header/protocol/diagnostic/MIR hashes;
- accepted/rejected corpus and acceptance-project summaries;
- prohibited Python semantic/backend import guard result;
- stage timings and terminal status.

The existing `reproducibility` gate remains Alpha.2 historical/trust evidence
until SH5 deliberately supersedes or composes it. Do not silently redefine its
schema or comparison contract.

## Completion evidence matrix

| Requirement | Required proof |
|---|---|
| Complete compiler source is expressible in Merit | Exact source-closure inventory plus stage-1/stage-2 compilation of every listed module |
| Normal project UX builds the compiler | Black-box subprocess test of the documented `merit-project build` command from a clean checkout |
| Output is a usable compiler | Stage 1 successfully compiles the full compiler project into stage 2 without private APIs |
| No Python production semantic authority | Runtime import/process guard plus code audit of the public path |
| Python remains an independent oracle | Differential tests execute the reference separately and compare contractual artifacts/behavior |
| Semantic equivalence | Complete accepted/rejected corpus, interpreter/native parity, and all acceptance projects |
| Deterministic equivalence | Stage-1/stage-2 canonical artifact and diagnostic hashes match |
| Fail-closed behavior | Missing, malformed, stale, incompatible, and unsupported inputs reject without fallback |
| Ownership/capability safety | Compiler-project lifecycle tests, explicit authority inventory, and native sanitizer/diagnostic evidence where available |
| Serialization and ABI stability | Existing representation tests plus byte-stable protocol/header fixtures |
| Cross-platform operation | Canonical self-hosting and full gates pass on Ubuntu and native Windows |
| Documentation accuracy | Status, architecture, bootstrap status, roadmap, manual/tooling docs, and limitations describe the verified boundary |

## Exit criteria

The self-hosting campaign closes only when:

- every required compiler source and non-source dependency is inventoried and
  classified;
- the complete compiler project builds through the documented normal project
  command into a directly usable next-stage compiler;
- production stage construction does not import or execute Python semantic,
  MIR-materialization, or C-emission authority;
- Python remains an independently executed oracle;
- stages 1 and 2 agree under the complete comparison contract from fresh
  isolated state;
- accepted/rejected corpus, acceptance projects, interpreter/native parity,
  serialization, ABI, ownership, contracts, capabilities, and deterministic
  diagnostics remain unchanged;
- focused, subsystem, full, corpus, replacement-acceptance, reproducibility, and
  self-hosting evidence passes at the required milestone boundaries;
- authoritative hosted Ubuntu and native-Windows self-hosting/full gates pass;
- documentation describes the actual public workflow and trust boundary; and
- the final PR stops for manual merge review. No release tag is created without
  explicit approval.

Only after this ledger closes may a later plan decide whether separate
compilation, dependency-granular caching, or Alpha.3 language work becomes the
next frontier.
