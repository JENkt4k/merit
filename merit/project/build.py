from __future__ import annotations

import contextlib
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess

from merit.compiler import CGenerator, Checker, Interpreter
from .loader import LoadedProject


def check(project: LoadedProject) -> Checker:
    return Checker(project.program).check()


def compile_cached_object(project: LoadedProject, c_path: Path, cache_root: Path, pic: bool = False) -> Path:
    compiler = os.environ.get("CC", "cc")
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
    command = [compiler, "-std=c11", "-Wall", "-Wextra"]
    if pic:
        command.append("-fPIC")
    command.extend((*project.manifest.c_flags, "-c", str(c_path), "-o", str(object_path)))
    subprocess.run(command, check=True)
    return object_path


def build(project: LoadedProject, output: Path) -> tuple[Path, Path, Path]:
    check(project)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    c_path = output.with_suffix(".c")
    h_path = output.with_suffix(".h")
    generator = CGenerator(project.program)
    c_path.write_text(generator.generate())
    h_path.write_text(generator.header())
    object_path = compile_cached_object(project, c_path, output.parent)
    command = [os.environ.get("CC", "cc"), str(object_path), *project.manifest.c_flags, "-o", str(output)]
    subprocess.run(command, check=True)
    return c_path, h_path, output


def build_shared(project: LoadedProject, output: Path) -> tuple[Path, Path, Path]:
    check(project)
    library = output.resolve()
    if library.suffix != ".so":
        library = library.with_suffix(".so")
    library.parent.mkdir(parents=True, exist_ok=True)
    c_path = library.with_suffix(".c")
    h_path = library.with_suffix(".h")
    generator = CGenerator(project.program)
    c_path.write_text(generator.generate())
    h_path.write_text(generator.header())
    object_path = compile_cached_object(project, c_path, library.parent, pic=True)
    command = [os.environ.get("CC", "cc"), "-shared", str(object_path), *project.manifest.c_flags, "-o", str(library)]
    subprocess.run(command, check=True)
    return c_path, h_path, library


def interpret(project: LoadedProject) -> str:
    check(project)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        Interpreter(project.program).run()
    return output.getvalue()
