"""Transport-only project discovery for production replacement compilation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .manifest import Manifest, load_manifest


_MODULE = re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_IMPORT = re.compile(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_]*)\s*;\s*$", re.MULTILINE)


class ReplacementProjectLoadError(ValueError):
    """Raised for project-envelope errors before the native frontend runs."""


@dataclass(frozen=True)
class ReplacementSourceUnit:
    path: Path
    module: str
    imports: tuple[str, ...]
    parser_source: str


@dataclass(frozen=True)
class ReplacementLoadedProject:
    manifest: Manifest
    units: tuple[ReplacementSourceUnit, ...]


def load_replacement_project(path: Path) -> ReplacementLoadedProject:
    """Discover source bytes without invoking the Python parser or checker."""

    manifest = load_manifest(path)
    found: set[Path] = set()
    for pattern in manifest.sources:
        found.update(candidate.resolve() for candidate in manifest.root.glob(pattern) if candidate.is_file())
    entry = manifest.entry_path.resolve()
    if not entry.is_file():
        raise ReplacementProjectLoadError(f"entry source does not exist: {entry}")
    found.add(entry)

    units: list[ReplacementSourceUnit] = []
    for source_path in sorted(found):
        source = source_path.read_text(encoding="utf-8")
        match = _MODULE.search(source)
        if match is None:
            raise ReplacementProjectLoadError(f"source has no module declaration: {source_path}")
        units.append(
            ReplacementSourceUnit(
                path=source_path,
                module=match.group(1),
                imports=tuple(_IMPORT.findall(source)),
                parser_source=source,
            )
        )
    return ReplacementLoadedProject(manifest, tuple(units))
