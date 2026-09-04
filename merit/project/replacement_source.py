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
_CAPABILITY_LINE = re.compile(
    r"^[ \t]*capability[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*;[ \t]*$",
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


def _deduplicate_project_capabilities(source: str, seen: set[str]) -> str:
    """Blank repeated declarations introduced only by project flattening.

    Each source unit has already been parsed and validated independently.  Two
    modules may therefore each declare the same capability even though a single
    source unit may not declare it twice.  The native project envelope flattens
    those validated units into one source buffer; retaining every declaration
    would manufacture a duplicate that did not exist in either unit.  Preserve
    the first declaration and width-blank later identical declarations so all
    following source offsets remain stable.
    """

    def normalize(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in seen:
            return _blank_match(match)
        seen.add(name)
        return match.group(0)

    return _CAPABILITY_LINE.sub(normalize, source)


def canonical_replacement_project_source(project: LoadedProject) -> str:
    """Join validated units without invoking reference semantic lowering.

    Unit order is the manifest loader's deterministic source-path order. Module
    and import syntax is blanked without changing source offsets, qualified
    project names retain width-preserving padding, repeated capability
    declarations created by flattening separately validated modules are blanked,
    and ``pub`` remains visible to the native frontend for export classification.
    """

    parts = [f"module {project.manifest.name}\n"]
    seen_capabilities: set[str] = set()
    for unit_index, _unit in enumerate(project.units):
        source = _native_unit_source(project, unit_index)
        source = _deduplicate_project_capabilities(source, seen_capabilities)
        parts.append(source)
        if not source.endswith("\n"):
            parts.append("\n")
    return "".join(parts)
