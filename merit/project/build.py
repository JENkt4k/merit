from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import subprocess

from merit.compiler import CGenerator, Checker, Interpreter
from .loader import LoadedProject


def check(project: LoadedProject) -> Checker:
    return Checker(project.program).check()


def build(project: LoadedProject, output: Path) -> tuple[Path, Path, Path]:
    check(project)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    c_path = output.with_suffix(".c")
    h_path = output.with_suffix(".h")
    generator = CGenerator(project.program)
    c_path.write_text(generator.generate())
    h_path.write_text(generator.header())
    command = [
        os.environ.get("CC", "cc"),
        "-std=c11",
        "-Wall",
        "-Wextra",
        *project.manifest.c_flags,
        str(c_path),
        "-o",
        str(output),
    ]
    subprocess.run(command, check=True)
    return c_path, h_path, output


def interpret(project: LoadedProject) -> str:
    check(project)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        Interpreter(project.program).run()
    return output.getvalue()
