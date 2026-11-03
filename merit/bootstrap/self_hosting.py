"""Public-interface stage construction and canonical SH5 comparison evidence.

This module transports source bytes, launches compiler processes, and compares
their output. It does not parse or lower Merit source in the production path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable

from merit.project.project_request import (
    ProjectRequest, ProjectRequestUnit, encode_loaded_project_request,
    encode_project_request,
)
from merit.project.replacement import (
    REPLACEMENT_MANIFEST, REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2,
    REPLACEMENT_SCHEMA,
)
from merit.project.replacement_loader import load_replacement_project


ROOT = Path(__file__).resolve().parents[2]
COMPILER_MANIFEST = ROOT / "compiler" / "Merit.toml"
COMPILER_SOURCE = ROOT / "examples" / "projects" / "bootstrap_lexer" / "src"
EXPECTED_COMPILER_MODULES = 46
SCHEMA = "merit-self-hosting-v1"
PROBE_TIMEOUT_SECONDS = 120
EXECUTABLE_TIMEOUT_SECONDS = 30
GUARDED_PYTHON_MODULES = (
    "merit.compiler", "merit.project.loader",
    "merit.bootstrap.resolved_source_function_snapshot",
    "merit.bootstrap.mir_contract", "merit.bootstrap.mir_to_c",
    "merit.bootstrap.replacement_project",
)
CORPUS_PATH = ROOT / "tests" / "project" / "alpha1_corpus_v1.json"
ACCEPTANCE_NAMES = (
    "text_pipeline", "binary_packet", "generic_result", "trait_bounds",
    "generic_collections", "borrowed_views", "bootstrap_lexer",
    "cobol_finance_modernization", "filesystem_capabilities", "ledger_app",
)


class SelfHostingError(RuntimeError):
    """The public stage or canonical comparison contract failed."""


@dataclass(frozen=True)
class Stage:
    name: str
    producer: Path | None
    project: Path
    executable: Path
    command: tuple[str, ...]
    build_seconds: float
    artifacts: dict[str, bytes]
    artifact_hashes: dict[str, str]
    protocol: str | None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_closure(source: Path = COMPILER_SOURCE) -> tuple[tuple[str, str], ...]:
    paths = tuple(sorted(source.rglob("*.mrt")))
    if len(paths) != EXPECTED_COMPILER_MODULES:
        raise SelfHostingError(
            f"compiler source closure has {len(paths)} modules, expected {EXPECTED_COMPILER_MODULES}"
        )
    return tuple((path.relative_to(source).as_posix(), sha256(path.read_bytes())) for path in paths)


def source_closure_digest(rows: tuple[tuple[str, str], ...]) -> str:
    return sha256(json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def isolated_compiler_project(destination: Path) -> Path:
    """Copy only the manifest and exact compiler source closure into a fresh root."""

    if destination.exists():
        raise SelfHostingError(f"isolated compiler root already exists: {destination}")
    project = destination / "compiler"
    source = destination / "examples" / "projects" / "bootstrap_lexer" / "src"
    project.mkdir(parents=True)
    shutil.copy2(COMPILER_MANIFEST, project / "Merit.toml")
    shutil.copytree(COMPILER_SOURCE, source)
    if source_closure(source) != source_closure():
        raise SelfHostingError("isolated compiler source closure differs from repository source")
    if any(path.exists() for path in (project / ".merit", project / "build", source / ".merit")):
        raise SelfHostingError("isolated compiler root contains prior build state")
    return project


def project_command() -> Path:
    executable = Path(sys.executable).with_name(
        "merit-project.exe" if os.name == "nt" else "merit-project"
    )
    if not executable.is_file():
        raise SelfHostingError(f"installed public project command is absent: {executable}")
    return executable


def _executable_path(output: Path) -> Path:
    return output.with_suffix(".exe") if os.name == "nt" else output


def _guarded_environment(root: Path) -> dict[str, str]:
    """Reject Python semantic/backend imports in the public CLI process."""

    root.mkdir(parents=True, exist_ok=True)
    script = (
        "import importlib.abc\n"
        "import sys\n"
        f"BLOCKED = {GUARDED_PYTHON_MODULES!r}\n"
        "class RejectSemanticImports(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname in BLOCKED:\n"
        "            raise RuntimeError('Python semantic import in public SH5 build: ' + fullname)\n"
        "        return None\n"
        "sys.meta_path.insert(0, RejectSemanticImports())\n"
    )
    (root / "sitecustomize.py").write_text(script, encoding="utf-8", newline="\n")
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(root) + (os.pathsep + existing if existing else "")
    return environment


def _read_artifacts(project: Path) -> tuple[dict[str, bytes], dict[str, str], str]:
    manifest = project / ".merit" / REPLACEMENT_MANIFEST
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelfHostingError(f"missing or invalid native artifact manifest: {manifest}") from exc
    if payload.get("schema") != REPLACEMENT_SCHEMA:
        raise SelfHostingError("native artifact manifest has an incompatible schema")
    metadata = payload.get("native_artifacts")
    expected = {"canonical_mir", "c_source", "c_header"}
    if not isinstance(metadata, dict) or set(metadata) != expected:
        raise SelfHostingError("native artifact manifest is incomplete")
    artifacts: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    root = manifest.parent.resolve()
    for label in sorted(expected):
        row = metadata[label]
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise SelfHostingError(f"invalid {label} artifact metadata")
        path = (root / row["path"]).resolve()
        try:
            path.relative_to(root)
            content = path.read_bytes()
        except (OSError, ValueError) as exc:
            raise SelfHostingError(f"invalid {label} artifact path") from exc
        digest = sha256(content)
        if not content or digest != row.get("sha256"):
            raise SelfHostingError(f"{label} artifact digest does not match")
        artifacts[label] = content
        digests[label] = digest
    protocol = payload.get("producer_protocol")
    if protocol != REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2:
        raise SelfHostingError("public build did not use the native v4 project protocol")
    return artifacts, digests, protocol


def build_seed(output: Path) -> Stage:
    """Build the trusted stage-0 seed through the independent reference oracle."""

    from merit.project.build import build
    from merit.project.loader import load_project

    started = time.monotonic()
    _, _, executable = build(load_project(COMPILER_MANIFEST), output)
    if not executable.is_file():
        raise SelfHostingError("reference stage-0 compiler was not produced")
    return Stage("stage_0", None, COMPILER_MANIFEST.parent, executable,
                 ("reference-build", str(COMPILER_MANIFEST), str(output)),
                 time.monotonic() - started, {}, {},
                 REPLACEMENT_NATIVE_ARTIFACT_PROTOCOL_V2)


def build_public_stage(name: str, project: Path, producer: Path, output: Path) -> Stage:
    """Build one usable compiler solely through the installed public command."""

    command = (str(project_command()), "build", str(project),
               "--compiler-path", str(producer), "-o", str(output))
    started = time.monotonic()
    completed = subprocess.run(
        command, capture_output=True, timeout=3600,
        env=_guarded_environment(output.parent / "semantic-import-guard"),
    )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise SelfHostingError(
            f"{name} public build failed ({completed.returncode}): "
            f"{completed.stderr.decode('utf-8', errors='replace')[-2000:]}"
        )
    executable = _executable_path(output)
    if completed.stdout.strip() != str(executable).encode() or not executable.is_file():
        raise SelfHostingError(f"{name} public build did not return a usable executable")
    artifacts, digests, protocol = _read_artifacts(project)
    return Stage(name, producer, project, executable, command, elapsed,
                 artifacts, digests, protocol)


def probe_request(source: bytes = b"module main\nfn main()->i32 { return 7; }\n") -> bytes:
    return encode_project_request(ProjectRequest(
        "sh5_probe", "src/main.mrt", (ProjectRequestUnit("src/main.mrt", source),),
        header_exports=(),
    ))


def run_probe(executable: Path, request: bytes) -> tuple[int, bytes, bytes]:
    completed = subprocess.run([str(executable)], input=request, capture_output=True,
                               timeout=PROBE_TIMEOUT_SECONDS)
    return completed.returncode, completed.stdout, completed.stderr


def _run_public(
    command: tuple[str, ...], *, cwd: Path | None = None,
    guard_root: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    environment = _guarded_environment(guard_root) if guard_root is not None else None
    return subprocess.run(command, cwd=cwd, capture_output=True, timeout=3600,
                          env=environment)


def _fresh_project(source: Path, destination: Path) -> Path:
    if destination.exists():
        raise SelfHostingError(f"project evidence root already exists: {destination}")
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        ".merit", ".merit-cache", "build", "__pycache__", "*.pyc",
    ))
    return destination


def _case_project(case: dict[str, object], destination: Path) -> Path:
    if destination.exists():
        raise SelfHostingError(f"corpus evidence root already exists: {destination}")
    destination.mkdir(parents=True)
    files = case["files"]
    if not isinstance(files, dict) or "src/main.mrt" not in files:
        raise SelfHostingError("corpus case has no canonical entry source")
    for relative, source in files.items():
        path = destination / str(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(source), encoding="utf-8", newline="\n")
    (destination / "Merit.toml").write_text(
        '[package]\n'
        f'name="alpha1_{str(case["id"]).replace("-", "_")}"\n'
        'entry="src/main.mrt"\n'
        'sources=["src/**/*.mrt"]\n',
        encoding="utf-8", newline="\n",
    )
    return destination


def _observable_tree(root: Path) -> tuple[tuple[str, str], ...]:
    ignored = {".merit", ".merit-cache", "build", "__pycache__"}
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in ignored for part in relative.parts):
            continue
        if path.suffix.lower() in {".o", ".obj", ".exe", ".dll", ".so", ".dylib"}:
            continue
        rows.append((relative.as_posix(), sha256(path.read_bytes())))
    return tuple(rows)


def _native_artifact_hashes(project: Path) -> dict[str, str]:
    return _read_artifacts(project)[1]


def _build_case(root: Path, compiler: Path | None, output: Path) -> tuple[tuple[int, bytes, bytes], dict[str, str], tuple[tuple[str, str], ...]]:
    command = (str(project_command()), "build", str(root), "-o", str(output))
    command += (("--compiler", "reference") if compiler is None else
                ("--compiler-path", str(compiler)))
    completed = _run_public(
        command, guard_root=output.parent / "semantic-import-guard" if compiler else None,
    )
    if completed.returncode != 0:
        raise SelfHostingError(
            f"accepted project public build failed: {root.name}: "
            f"{completed.stderr.decode('utf-8', errors='replace')[-2000:]}"
        )
    executable = _executable_path(output)
    if completed.stdout.strip() != str(executable).encode() or not executable.is_file():
        raise SelfHostingError(f"accepted project build produced no executable: {root.name}")
    run = subprocess.run([str(executable)], cwd=root, capture_output=True,
                         timeout=EXECUTABLE_TIMEOUT_SECONDS)
    observation = (run.returncode, run.stdout, run.stderr)
    if run.returncode != 0:
        raise SelfHostingError(f"accepted project exited {run.returncode}: {root.name}")
    artifacts = {} if compiler is None else _native_artifact_hashes(root)
    return observation, artifacts, _observable_tree(root)


def _reference_rejects(root: Path) -> None:
    completed = _run_public((str(project_command()), "check", str(root),
                             "--compiler", "reference"))
    if completed.returncode == 0:
        raise SelfHostingError(f"Python oracle accepted rejected corpus case: {root.name}")


def _stage_rejection(stage: Stage, root: Path) -> tuple[int, bytes, bytes]:
    request = encode_loaded_project_request(load_replacement_project(root / "Merit.toml"),
                                            header_exports=frozenset())
    protocol_observation = run_probe(stage.executable, request)
    completed = _run_public((str(project_command()), "build", str(root),
                             "--compiler-path", str(stage.executable),
                             "-o", str(root / "rejected")),
                            guard_root=root / "semantic-import-guard")
    if completed.returncode == 0:
        raise SelfHostingError(f"stage {stage.name} accepted rejected corpus case: {root.name}")
    return protocol_observation


def verify_fixed_corpus(
    stages: tuple[Stage, Stage, Stage], output_root: Path,
    *, progress: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Compare the fixed Alpha.1 corpus across all stages and the independent oracle."""

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if corpus.get("contract") != "alpha1-corpus-convergence-v1":
        raise SelfHostingError("unsupported fixed corpus contract")
    accepted: dict[str, object] = {}
    rejected: dict[str, object] = {}
    for case in corpus["accepted"]:
        name = str(case["id"])
        if progress:
            progress(f"corpus_accepted/{name}", "started")
        case_root = output_root / "accepted" / name
        reference_root = _case_project(case, case_root / "reference")
        reference = _build_case(reference_root, None, case_root / "reference-bin")
        request = encode_loaded_project_request(
            load_replacement_project(reference_root / "Merit.toml"),
            header_exports=frozenset(),
        )
        protocol_observations = tuple(run_probe(stage.executable, request) for stage in stages)
        if len(set(protocol_observations)) != 1 or protocol_observations[0][0] != 0:
            raise SelfHostingError(f"accepted corpus compiler protocol differs: {name}")
        observations = []
        hashes = []
        for stage in stages:
            root = _case_project(case, case_root / stage.name)
            observation, artifact_hashes, tree = _build_case(
                root, stage.executable, case_root / f"{stage.name}-bin",
            )
            observations.append((observation, tree))
            hashes.append(artifact_hashes)
        if any(row != (reference[0], reference[2]) for row in observations):
            raise SelfHostingError(f"accepted corpus runtime or file effects differ: {name}")
        if not hashes[0] == hashes[1] == hashes[2]:
            raise SelfHostingError(f"accepted corpus canonical artifacts differ: {name}")
        accepted[name] = {
            "runtime_sha256": sha256(repr(reference[0]).encode()),
            "protocol_sha256": sha256(protocol_observations[0][1]),
            "observable_tree": list(reference[2]),
            "canonical_artifact_sha256": hashes[0],
        }
        if progress:
            progress(f"corpus_accepted/{name}", "passed")
    for case in corpus["rejected"]:
        name = str(case["id"])
        if progress:
            progress(f"corpus_rejected/{name}", "started")
        case_root = output_root / "rejected" / name
        _reference_rejects(_case_project(case, case_root / "reference"))
        observations = tuple(_stage_rejection(stage, _case_project(
            case, case_root / stage.name,
        )) for stage in stages)
        if len(set(observations)) != 1:
            raise SelfHostingError(f"rejected corpus protocol/diagnostics differ: {name}")
        rejected[name] = {
            "native_status": observations[0][0],
            "protocol_sha256": sha256(observations[0][1]),
            "diagnostic_sha256": sha256(observations[0][2]),
        }
        if progress:
            progress(f"corpus_rejected/{name}", "passed")
    return {"contract": corpus["contract"], "accepted": accepted, "rejected": rejected,
            "accepted_count": len(accepted), "rejected_count": len(rejected)}


def verify_acceptance_projects(
    stages: tuple[Stage, Stage, Stage], output_root: Path,
    *, progress: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Execute all ten acceptance projects through public stage builds and oracle."""

    results: dict[str, object] = {}
    for name in ACCEPTANCE_NAMES:
        if progress:
            progress(f"acceptance/{name}", "started")
        source = ROOT / "examples" / "projects" / name
        case_root = output_root / name
        reference_root = _fresh_project(source, case_root / "reference")
        reference_observation, _, reference_tree = _build_case(
            reference_root, None, case_root / "reference-bin",
        )
        artifact_hashes = []
        for stage in stages:
            root = _fresh_project(source, case_root / stage.name)
            observation, hashes, tree = _build_case(
                root, stage.executable, case_root / f"{stage.name}-bin",
            )
            if (observation, tree) != (reference_observation, reference_tree):
                raise SelfHostingError(f"acceptance runtime or file effects differ: {name}")
            artifact_hashes.append(hashes)
        if not artifact_hashes[0] == artifact_hashes[1] == artifact_hashes[2]:
            raise SelfHostingError(f"acceptance canonical artifacts differ: {name}")
        results[name] = {"runtime_sha256": sha256(repr(reference_observation).encode()),
                         "canonical_artifact_sha256": artifact_hashes[0]}
        if progress:
            progress(f"acceptance/{name}", "passed")
    return {"count": len(results), "projects": results}


def compare_stage_bytes(stages: tuple[Stage, Stage, Stage]) -> dict[str, object]:
    """Compare stage-1/2 artifacts and stage-0/1/2 fixed protocol probes."""

    stage0, stage1, stage2 = stages
    if stage1.protocol != stage2.protocol or not stage1.protocol:
        raise SelfHostingError("stage-1/stage-2 native artifact protocols differ")
    for label in ("canonical_mir", "c_source", "c_header"):
        if stage1.artifacts.get(label) != stage2.artifacts.get(label):
            raise SelfHostingError(f"stage-1/stage-2 {label} bytes differ")
    accepted = probe_request()
    rejected = (accepted[:4] + (99).to_bytes(4, "big") + accepted[8:], probe_request(
        b"module main\nimport missing;\nfn main()->i32 { return 7; }\n"
    ))
    results: dict[str, object] = {}
    for label, request, should_accept in (
        ("accepted", accepted, True),
        ("malformed_request", rejected[0], False),
        ("missing_import", rejected[1], False),
    ):
        observations = tuple(run_probe(stage.executable, request) for stage in stages)
        if len(set(observations)) != 1:
            raise SelfHostingError(f"stage-0/stage-1/stage-2 {label} protocol or diagnostics differ")
        status, stdout, stderr = observations[0]
        if (status == 0) != should_accept:
            raise SelfHostingError(f"{label} has unexpected compiler exit status {status}")
        results[label] = {
            "returncode": status,
            "stdout_sha256": sha256(stdout),
            "stderr_sha256": sha256(stderr),
            "request_sha256": sha256(request),
        }
    return {"canonical_artifact_sha256": stage1.artifact_hashes,
            "fixed_probes": results}


def build_stages(
    output_root: Path, *, progress: Callable[[str, str], None] | None = None,
) -> tuple[Stage, Stage, Stage]:
    """Construct fresh public stages, returning their paths and verified artifacts."""

    if output_root.exists():
        raise SelfHostingError(f"self-hosting evidence root already exists: {output_root}")
    output_root.mkdir(parents=True)
    stage0 = build_seed(output_root / "stage-0" / "merit-frontend")
    stages = [stage0]
    for name in ("stage_1", "stage_2"):
        if progress:
            progress(name, "started")
        project = isolated_compiler_project(output_root / f"{name}-source")
        producer = stages[-1].executable
        stage = build_public_stage(name, project, producer,
                                   output_root / name / "merit-frontend")
        stages.append(stage)
        if progress:
            progress(name, "passed")
    return stages[0], stages[1], stages[2]


def stage_equivalence_evidence(stages: tuple[Stage, Stage, Stage]) -> dict[str, object]:
    comparison = compare_stage_bytes(stages)
    rows = source_closure()
    return {
        "schema": SCHEMA,
        "status": "stage-equivalence-passed",
        "source_closure": {"count": len(rows), "digest_sha256": source_closure_digest(rows),
                           "paths": [path for path, _ in rows]},
        "stages": {stage.name: {
            "producer": str(stage.producer) if stage.producer else "reference-oracle",
            "executable": str(stage.executable),
            "executable_sha256": sha256(stage.executable.read_bytes()),
            "command": list(stage.command),
            "project": str(stage.project), "build_seconds": round(stage.build_seconds, 3),
            "protocol": stage.protocol, "artifact_sha256": stage.artifact_hashes,
        } for stage in stages},
        "isolated_source_build_cache_roots": True,
        "public_build_python_semantic_import_guard": list(GUARDED_PYTHON_MODULES),
        "comparison": comparison,
    }


def build_stage_equivalence(
    output_root: Path, *, progress: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Construct fresh public stages and return the bounded core SH5 evidence."""

    return stage_equivalence_evidence(build_stages(output_root, progress=progress))


def _git_identity() -> dict[str, object]:
    commit = subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(("git", "status", "--porcelain", "--untracked-files=all"),
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return {"commit": commit, "dirty": bool(status.strip())}


def _toolchain_identity() -> dict[str, str]:
    compiler = os.environ.get("CC") or next((path for name in ("cc", "gcc", "clang")
                                         if (path := shutil.which(name))), None)
    if compiler is None:
        raise SelfHostingError("external C compiler is unavailable")
    version = subprocess.run((compiler, "--version"), capture_output=True,
                             text=True, check=True).stdout.splitlines()[0]
    return {"path": str(compiler), "version": version}


def _python_import_guard(output_root: Path) -> dict[str, object]:
    test = "tests/bootstrap/test_replacement_prepare.py::test_public_v4_build_never_imports_python_semantic_backend"
    command = (sys.executable, "-m", "pytest", "-q", test,
               f"--basetemp={output_root / 'guard-pytest'}")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
    if completed.returncode != 0:
        raise SelfHostingError("public build Python semantic/backend import guard failed: "
                               + completed.stdout.decode("utf-8", errors="replace")[-1200:])
    return {"status": "passed", "test": test, "command": list(command)}


def build_self_hosting_evidence(
    output_root: Path, *, progress: Callable[[str, str], None] | None = None,
) -> dict[str, object]:
    """Run the complete SH5 stage, corpus, acceptance, and import-guard contract."""

    started = time.monotonic()
    stages = build_stages(output_root / "stages", progress=progress)
    payload = stage_equivalence_evidence(stages)
    if progress:
        progress("fixed_corpus", "started")
    payload["fixed_corpus"] = verify_fixed_corpus(
        stages, output_root / "corpus", progress=progress,
    )
    if progress:
        progress("fixed_corpus", "passed")
        progress("acceptance_projects", "started")
    payload["acceptance_projects"] = verify_acceptance_projects(
        stages, output_root / "acceptance", progress=progress,
    )
    if progress:
        progress("acceptance_projects", "passed")
        progress("python_import_guard", "started")
    payload["python_import_guard"] = _python_import_guard(output_root)
    if progress:
        progress("python_import_guard", "passed")
    payload.update(
        status="passed",
        repository=_git_identity(),
        platform=sys.platform,
        python=sys.version.split()[0],
        external_c_toolchain=_toolchain_identity(),
        duration_seconds=round(time.monotonic() - started, 3),
    )
    return payload
