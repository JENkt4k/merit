"""Deterministic textual project envelope for the native replacement frontend."""

from __future__ import annotations

import re

from merit.project.loader import LoadedProject


_MODULE_LINE = re.compile(
    r"^[ \t]*module[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t]*$",
    re.MULTILINE,
)
_IMPORT_LINE = re.compile(
    r"^[ \t]*import[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t]*;[ \t]*$",
    re.MULTILINE,
)


def _blank_match(match: re.Match[str]) -> str:
    return "".join("\n" if character == "\n" else " " for character in match.group(0))


def _native_unit_source(project: LoadedProject, unit_index: int) -> str:
    unit = project.units[unit_index]
    source = unit.path.read_text(encoding="utf-8")
    source = _MODULE_LINE.sub(_blank_match, source, count=1)
    source = _IMPORT_LINE.sub(_blank_match, source)
    module_names = {candidate.module for candidate in project.units}

    def unqualify(match: re.Match[str]) -> str:
        qualifier = match.group(1)
        if qualifier not in module_names:
            return match.group(0)
        return " " * (len(qualifier) + 1) + match.group(2)

    return re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b",
        unqualify,
        source,
    )


def canonical_replacement_project_source(project: LoadedProject) -> str:
    """Join validated units without invoking reference semantic lowering.

    Unit order is the manifest loader's deterministic source-path order. Module
    and import syntax is blanked without changing source offsets, qualified
    project names retain width-preserving padding, and ``pub`` remains visible
    to the native frontend for export classification.
    """

    parts = [f"module {project.manifest.name}\n"]
    for unit_index, _unit in enumerate(project.units):
        source = _native_unit_source(project, unit_index)
        parts.append(source)
        if not source.endswith("\n"):
            parts.append("\n")
    return "".join(parts)
