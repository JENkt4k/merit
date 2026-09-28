from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Manifest:
    root: Path
    name: str
    entry: str
    sources: tuple[str, ...]
    c_flags: tuple[str, ...]
    executable_adapter: str | None = None
    executable_entry: str | None = None

    @property
    def entry_path(self) -> Path:
        return self.root / self.entry


def load_manifest(path: Path) -> Manifest:
    path = path.resolve()
    data = tomllib.loads(path.read_text())
    package = data.get("package", {})
    build = data.get("build", {})
    executable = data.get("executable", {})
    name = package.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("manifest requires package.name")
    entry = package.get("entry", "src/main.mrt")
    sources = package.get("sources", ["src/**/*.mrt"])
    if not isinstance(sources, list) or not all(isinstance(x, str) for x in sources):
        raise ValueError("package.sources must be an array of glob strings")
    c_flags = build.get("c_flags", ["-O2"])
    if not isinstance(c_flags, list) or not all(isinstance(x, str) for x in c_flags):
        raise ValueError("build.c_flags must be an array of strings")
    if not isinstance(executable, dict):
        raise ValueError("executable must be a table")
    executable_adapter = executable.get("adapter")
    executable_entry = executable.get("entry")
    if executable_adapter is None and executable_entry is None:
        pass
    elif executable_adapter != "stdin-string-i32":
        raise ValueError("executable.adapter must be 'stdin-string-i32'")
    elif not isinstance(executable_entry, str) or not executable_entry.isidentifier():
        raise ValueError("executable.entry must be a non-empty Merit identifier")
    return Manifest(
        path.parent,
        name,
        entry,
        tuple(sources),
        tuple(c_flags),
        executable_adapter,
        executable_entry,
    )
