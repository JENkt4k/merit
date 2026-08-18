"""Build the concrete Merit-native replacement frontend driver.

The resulting artifact is a native executable. A tiny C host owns only process
I/O: it reads stdin into a stable ``merit_String`` view and calls the exported
Merit frontend entrypoint. Target-source lexing and semantic lowering remain in
Merit code; the host does not inspect or reinterpret source text.
"""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from merit.project.build import NativeBuildError, build_shared
from merit.project.loader import load_project
from merit.project.replacement_prepare import NativeReplacementDriver


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_PROJECT = ROOT / "examples" / "projects" / "bootstrap_lexer" / "Merit.toml"


def _compiler() -> str:
    configured = os.environ.get("CC")
    if configured:
        if shutil.which(configured) is not None or Path(configured).is_file():
            return configured
        raise NativeBuildError(127, [configured], f"C compiler {configured!r} was not found")
    for candidate in ("cc", "gcc", "clang"):
        if shutil.which(candidate):
            return candidate
    raise NativeBuildError(127, ["cc"], "No supported C compiler was found for the replacement driver host")


def _host_source(header_name: str) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "{header_name}"

int main(void) {{
    char *data = NULL;
    size_t length = 0;
    size_t capacity = 0;
    unsigned char chunk[4096];
    for (;;) {{
        size_t got = fread(chunk, 1, sizeof(chunk), stdin);
        if (got != 0) {{
            size_t needed = length + got;
            if (needed > capacity) {{
                size_t next = capacity ? capacity : 4096;
                while (next < needed) {{
                    if (next > ((size_t)-1) / 2) {{ fputs("replacement driver input is too large\\n", stderr); free(data); return 64; }}
                    next *= 2;
                }}
                char *grown = (char *)realloc(data, next);
                if (grown == NULL) {{ fputs("replacement driver input allocation failed\\n", stderr); free(data); return 65; }}
                data = grown;
                capacity = next;
            }}
            for (size_t index = 0; index < got; ++index) data[length + index] = (char)chunk[index];
            length = needed;
        }}
        if (got < sizeof(chunk)) {{
            if (ferror(stdin)) {{ fputs("replacement driver could not read stdin\\n", stderr); free(data); return 66; }}
            break;
        }}
    }}
    merit_String source = {{ data, length }};
    int32_t status = merit_emit_replacement_bundle(source);
    free(data);
    return (int)status;
}}
'''


def build_native_replacement_driver(output: Path) -> NativeReplacementDriver:
    """Build and return the concrete native frontend driver executable."""

    output = output.expanduser().resolve()
    if sys.platform.startswith("win") and output.suffix.lower() != ".exe":
        output = output.with_suffix(".exe")
    output.parent.mkdir(parents=True, exist_ok=True)

    project = load_project(BOOTSTRAP_PROJECT)
    _, header, library = build_shared(project, output.parent / "merit-replacement-frontend")
    host = output.with_suffix(".host.c")
    host.write_text(_host_source(header.name), encoding="utf-8", newline="\n")

    command = [
        _compiler(),
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-I",
        str(header.parent),
        str(host),
        str(library),
    ]
    if sys.platform == "darwin":
        command.extend(("-Wl,-rpath,@loader_path",))
    elif not sys.platform.startswith("win"):
        command.extend(("-Wl,-rpath,$ORIGIN",))
    command.extend(("-o", str(output)))

    completed = subprocess.run(command, text=True, capture_output=True, errors="replace")
    if completed.returncode != 0:
        shown = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
        detail = [
            f"native replacement driver host linking failed with exit code {completed.returncode}",
            f"command: {shown}",
            f"generated header: {header}",
            f"frontend library: {library}",
            f"host source: {host}",
        ]
        if completed.stdout:
            detail.extend(("stdout:", completed.stdout.rstrip()))
        if completed.stderr:
            detail.extend(("stderr:", completed.stderr.rstrip()))
        raise NativeBuildError(
            completed.returncode,
            command,
            "\n".join(detail),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    return NativeReplacementDriver(output)
