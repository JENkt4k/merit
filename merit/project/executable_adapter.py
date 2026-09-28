"""Generic native executable adapters for stable exported Merit functions.

Adapters provide process I/O only. They do not inspect Merit source or alter
program semantics. The first contract reads stdin into the stable ``String``
ABI, calls one exported ``String -> i32`` Merit function, and returns its status.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .build import _compiler, _native_environment, _run_native_command


STDIN_STRING_I32_ADAPTER = "stdin-string-i32"


def _stdin_string_i32_host_source(entry: str) -> str:
    if not entry.isidentifier():
        raise ValueError("stdin-string-i32 entry must be a Merit identifier")
    return f'''#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {{
    const uint8_t *data;
    size_t len;
}} merit_String;

extern int32_t merit_{entry}(merit_String source_text);

int main(void) {{
    uint8_t *data = NULL;
    size_t length = 0;
    size_t capacity = 0;
    uint8_t chunk[4096];
    for (;;) {{
        size_t got = fread(chunk, 1, sizeof(chunk), stdin);
        if (got != 0) {{
            size_t needed = length + got;
            if (needed > capacity) {{
                size_t next = capacity ? capacity : 4096;
                while (next < needed) {{
                    if (next > ((size_t)-1) / 2) {{ fputs("adapter input is too large\\n", stderr); free(data); return 64; }}
                    next *= 2;
                }}
                uint8_t *grown = (uint8_t *)realloc(data, next);
                if (grown == NULL) {{ fputs("adapter input allocation failed\\n", stderr); free(data); return 65; }}
                data = grown;
                capacity = next;
            }}
            for (size_t index = 0; index < got; ++index) data[length + index] = chunk[index];
            length = needed;
        }}
        if (got < sizeof(chunk)) {{
            if (ferror(stdin)) {{ fputs("adapter could not read stdin\\n", stderr); free(data); return 66; }}
            break;
        }}
    }}
    merit_String source = {{ data, length }};
    int32_t status = merit_{entry}(source);
    if (status != 0) fprintf(stderr, "replacement driver status %d\\n", status);
    free(data);
    return (int)status;
}}
'''


def link_executable_adapter(
    output: Path,
    *,
    library: Path,
    adapter: str,
    entry: str,
) -> Path:
    """Link a generic process adapter to an already-built Merit library."""

    if adapter != STDIN_STRING_I32_ADAPTER:
        raise ValueError(f"unsupported executable adapter: {adapter!r}")
    output = output.expanduser().resolve()
    if sys.platform.startswith("win") and output.suffix.lower() != ".exe":
        output = output.with_suffix(".exe")
    output.parent.mkdir(parents=True, exist_ok=True)
    host = output.with_suffix(".host.c")
    host.write_text(_stdin_string_i32_host_source(entry), encoding="utf-8", newline="\n")

    command = [_compiler(), "-std=c11", "-Wall", "-Wextra", str(host), str(library)]
    if sys.platform == "darwin":
        command.extend(("-Wl,-rpath,@loader_path",))
    elif not sys.platform.startswith("win"):
        command.extend(("-Wl,-rpath,$ORIGIN",))
    command.extend(("-o", str(output)))
    _run_native_command(
        command,
        phase="executable-adapter linking",
        artifacts=(host, library, output),
        environment=_native_environment(output.parent),
    )
    return output
