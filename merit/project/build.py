from __future__ import annotations

import contextlib
import hashlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from merit.compiler import CGenerator, Checker, Interpreter
from .loader import LoadedProject


class NativeBuildError(subprocess.CalledProcessError):
    """A native toolchain command failed with actionable diagnostics.

    This remains a ``CalledProcessError`` for compatibility with callers that
    historically caught subprocess failures, while presenting a deterministic
    human-readable message with commands and artifact locations.
    """

    def __init__(
        self,
        returncode: int,
        command: list[str],
        message: str,
        *,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(returncode, command, output=stdout, stderr=stderr)
        self.message = message

    def __str__(self) -> str:
        return self.message


def check(project: LoadedProject) -> Checker:
    return Checker(project.program).check()


def _windows_msys2_root() -> Path | None:
    configured = os.environ.get("MSYS2_ROOT")
    candidates = [
        Path(configured) if configured else None,
        Path("C:/msys64"),
        Path("D:/msys64"),
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "ucrt64" / "bin" / "gcc.exe").is_file():
            return candidate.resolve()
    return None


def _compiler() -> str:
    configured = os.environ.get("CC")
    if configured:
        resolved = shutil.which(configured)
        if resolved is None and not Path(configured).is_file():
            raise NativeBuildError(
                127,
                [configured],
                f"C compiler {configured!r} was not found. "
                "Install GCC or Clang, or correct the CC environment variable.",
            )
        return configured

    for candidate in ("cc", "gcc", "clang"):
        if shutil.which(candidate):
            return candidate

    if os.name == "nt":
        root = _windows_msys2_root()
        if root is not None:
            return str(root / "ucrt64" / "bin" / "gcc.exe")

    raise NativeBuildError(
        127,
        ["cc"],
        "No supported C compiler was found. Install GCC or Clang, or set CC.",
    )


def _display_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _native_environment(working_temp: Path | None = None) -> dict[str, str]:
    environment = os.environ.copy()

    if working_temp is not None:
        working_temp.mkdir(parents=True, exist_ok=True)
        environment["TEMP"] = str(working_temp)
        environment["TMP"] = str(working_temp)

    if os.name != "nt":
        return environment

    root = _windows_msys2_root()
    if root is None:
        return environment

    ucrt_bin = str(root / "ucrt64" / "bin")
    usr_bin = str(root / "usr" / "bin")
    existing = environment.get("PATH", "")
    entries = [ucrt_bin, usr_bin]
    entries.extend(
        entry
        for entry in existing.split(os.pathsep)
        if entry and entry.casefold() not in {ucrt_bin.casefold(), usr_bin.casefold()}
    )
    environment["PATH"] = os.pathsep.join(entries)
    environment["MSYSTEM"] = "UCRT64"
    environment["MINGW_PREFIX"] = "/ucrt64"
    environment["MSYSTEM_PREFIX"] = "/ucrt64"
    environment["CHERE_INVOKING"] = "1"

    # These variables can redirect GCC internals to another installation and
    # caused silent cc1 failures in ordinary PowerShell sessions.
    for name in (
        "GCC_EXEC_PREFIX",
        "COMPILER_PATH",
        "LIBRARY_PATH",
        "CPATH",
        "C_INCLUDE_PATH",
        "CPLUS_INCLUDE_PATH",
    ):
        environment.pop(name, None)

    return environment


def _run_native_command(
    command: list[str],
    *,
    phase: str,
    artifacts: tuple[Path, ...] = (),
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        errors="replace",
        env=environment,
    )
    if completed.returncode == 0:
        return completed

    details = [
        f"native {phase} failed with exit code {completed.returncode}",
        f"command: {_display_command(command)}",
    ]
    if artifacts:
        details.append("artifacts:")
        details.extend(f"  {artifact.resolve()}" for artifact in artifacts)
    if completed.stdout:
        details.extend(("stdout:", completed.stdout.rstrip()))
    if completed.stderr:
        details.extend(("stderr:", completed.stderr.rstrip()))
    raise NativeBuildError(
        completed.returncode,
        command,
        "\n".join(details),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _native_executable_path(output: Path, platform: str | None = None) -> Path:
    platform = platform or sys.platform
    if platform.startswith("win") and output.suffix.lower() != ".exe":
        return output.with_suffix(".exe")
    return output


def _temporary_object_path(cache_dir: Path, object_path: Path) -> Path:
    """Reserve a unique name but let the compiler create the output file.

    Pre-created output files can be held open briefly by Windows antivirus or
    indexing software. Creating a name and unlinking it before invoking GCC
    avoids that race while preserving atomic replacement into the cache.
    """

    descriptor, name = tempfile.mkstemp(
        prefix=f"{object_path.stem}-",
        suffix=f".tmp{object_path.suffix}",
        dir=cache_dir,
    )
    os.close(descriptor)
    temporary_path = Path(name)
    temporary_path.unlink()
    return temporary_path


def compile_cached_object(
    project: LoadedProject,
    c_path: Path,
    cache_root: Path,
    pic: bool = False,
) -> Path:
    compiler = _compiler()
    compiler_path = Path(shutil.which(compiler) or compiler).resolve()
    digest = hashlib.sha256()
    digest.update(c_path.read_bytes())
    digest.update(str(compiler_path).encode())
    try:
        compiler_stat = compiler_path.stat()
        digest.update(f"{compiler_stat.st_size}:{compiler_stat.st_mtime_ns}".encode())
    except OSError:
        pass
    digest.update(repr(project.manifest.c_flags).encode())
    digest.update(b"pic" if pic else b"exe")
    cache_dir = cache_root / ".merit-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    object_path = cache_dir / f"{digest.hexdigest()[:24]}.o"
    if object_path.exists():
        return object_path

    temporary_path = _temporary_object_path(cache_dir, object_path)
    command = [compiler, "-std=c11", "-Wall", "-Wextra"]
    if pic:
        command.append("-fPIC")
    command.extend(
        (*project.manifest.c_flags, "-c", str(c_path), "-o", str(temporary_path))
    )
    try:
        _run_native_command(
            command,
            phase="compilation",
            artifacts=(c_path, temporary_path),
            environment=_native_environment(cache_dir),
        )
        os.replace(temporary_path, object_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return object_path


def build(project: LoadedProject, output: Path) -> tuple[Path, Path, Path]:
    check(project)
    output = _native_executable_path(output.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    c_path = output.with_suffix(".c")
    h_path = output.with_suffix(".h")
    generator = CGenerator(project.program)
    c_path.write_text(generator.generate(), encoding="utf-8", newline="\n")
    h_path.write_text(generator.header(), encoding="utf-8", newline="\n")
    object_path = compile_cached_object(project, c_path, output.parent)
    command = [
        _compiler(),
        str(object_path),
        *project.manifest.c_flags,
        "-o",
        str(output),
    ]
    _run_native_command(
        command,
        phase="linking",
        artifacts=(c_path, h_path, object_path, output),
        environment=_native_environment(output.parent / ".merit-cache"),
    )
    return c_path, h_path, output


def shared_library_policy(
    platform: str | None = None,
) -> tuple[str, tuple[str, ...], bool]:
    platform = platform or sys.platform
    if platform == "darwin":
        return ".dylib", ("-dynamiclib",), True
    if platform.startswith("win"):
        return ".dll", ("-shared",), False
    return ".so", ("-shared",), True


def build_shared(project: LoadedProject, output: Path) -> tuple[Path, Path, Path]:
    check(project)
    suffix, link_flags, pic = shared_library_policy()
    library = output.resolve()
    if library.suffix != suffix:
        library = library.with_suffix(suffix)
    library.parent.mkdir(parents=True, exist_ok=True)
    c_path = library.with_suffix(".c")
    h_path = library.with_suffix(".h")
    generator = CGenerator(project.program)
    c_path.write_text(generator.generate(), encoding="utf-8", newline="\n")
    h_path.write_text(generator.header(), encoding="utf-8", newline="\n")
    object_path = compile_cached_object(project, c_path, library.parent, pic=pic)
    command = [
        _compiler(),
        *link_flags,
        str(object_path),
        *project.manifest.c_flags,
        "-o",
        str(library),
    ]
    _run_native_command(
        command,
        phase="shared-library linking",
        artifacts=(c_path, h_path, object_path, library),
        environment=_native_environment(library.parent / ".merit-cache"),
    )
    return c_path, h_path, library


def interpret(project: LoadedProject) -> str:
    check(project)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        Interpreter(project.program).run()
    return output.getvalue()
