"""Transport-only project discovery for production replacement compilation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import Manifest, load_manifest


class ReplacementProjectLoadError(ValueError):
    """Raised for project-envelope errors before the native frontend runs."""


@dataclass(frozen=True)
class ReplacementSourceUnit:
    path: Path
    source: bytes


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
        units.append(ReplacementSourceUnit(path=source_path, source=source_path.read_bytes()))
    return ReplacementLoadedProject(manifest, tuple(units))
