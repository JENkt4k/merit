"""Versioned, transport-only project request for the native compiler.

The host owns deterministic file discovery and byte transport. It deliberately
does not discover Merit modules, imports, capabilities, or any other source
semantics. Those remain the native compiler's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable


PROJECT_REQUEST_MAGIC = b"MPRQ"
PROJECT_REQUEST_VERSION = 1
PROJECT_REQUEST_EXPORT_VERSION = 2


class ProjectRequestError(ValueError):
    """Raised when a project request is malformed or non-canonical."""


@dataclass(frozen=True)
class ProjectRequestUnit:
    path: str
    source: bytes


@dataclass(frozen=True)
class ProjectRequest:
    package: str
    entry: str
    units: tuple[ProjectRequestUnit, ...]
    header_exports: tuple[str, ...] | None = None


def _u32(value: int) -> bytes:
    if value < 0 or value > 0xFFFF_FFFF:
        raise ProjectRequestError("project request field exceeds u32 framing")
    return value.to_bytes(4, "big")


def _field(value: bytes) -> bytes:
    return _u32(len(value)) + value


def _canonical_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ProjectRequestError(f"project request path is not canonical: {value!r}")
    return value


def encode_project_request(request: ProjectRequest) -> bytes:
    try:
        package = request.package.encode("utf-8")
        entry = _canonical_path(request.entry).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProjectRequestError("project request metadata must be UTF-8") from exc
    if not package:
        raise ProjectRequestError("project request package is empty")
    if not request.units:
        raise ProjectRequestError("project request has no source units")

    encoded = bytearray(PROJECT_REQUEST_MAGIC)
    explicit_exports = request.header_exports is not None
    encoded.extend(_u32(PROJECT_REQUEST_EXPORT_VERSION if explicit_exports else PROJECT_REQUEST_VERSION))
    encoded.extend(_field(package))
    encoded.extend(_field(entry))
    if explicit_exports:
        assert request.header_exports is not None
        encoded.extend(_u32(len(request.header_exports)))
        previous_export = ""
        for name in request.header_exports:
            if not name.isascii() or not name.isidentifier() or (previous_export and name <= previous_export):
                raise ProjectRequestError("project request header exports must be unique sorted ASCII identifiers")
            previous_export = name
            encoded.extend(_field(name.encode("utf-8")))
    encoded.extend(_u32(len(request.units)))
    previous = ""
    entry_found = False
    for unit in request.units:
        path = _canonical_path(unit.path)
        if previous and path <= previous:
            raise ProjectRequestError("project request units must be uniquely path-sorted")
        previous = path
        entry_found = entry_found or path == request.entry
        try:
            path_bytes = path.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ProjectRequestError("project request paths must be UTF-8") from exc
        encoded.extend(_field(path_bytes))
        encoded.extend(_field(bytes(unit.source)))
    if not entry_found:
        raise ProjectRequestError("project request entry is absent from source units")
    return bytes(encoded)


def decode_project_request(data: bytes) -> ProjectRequest:
    """Independent host oracle for framing tests; not used by production builds."""

    position = 0

    def take(length: int) -> bytes:
        nonlocal position
        end = position + length
        if length < 0 or end > len(data):
            raise ProjectRequestError("project request is truncated")
        value = data[position:end]
        position = end
        return value

    def integer() -> int:
        return int.from_bytes(take(4), "big")

    def field() -> bytes:
        return take(integer())

    if take(4) != PROJECT_REQUEST_MAGIC:
        raise ProjectRequestError("project request has invalid magic")
    version = integer()
    if version not in (PROJECT_REQUEST_VERSION, PROJECT_REQUEST_EXPORT_VERSION):
        raise ProjectRequestError(f"unsupported project request version {version}")
    try:
        package = field().decode("utf-8")
        entry = field().decode("utf-8")
        header_exports = (
            tuple(field().decode("utf-8") for _ in range(integer()))
            if version == PROJECT_REQUEST_EXPORT_VERSION else None
        )
        count = integer()
        units = tuple(
            ProjectRequestUnit(field().decode("utf-8"), field()) for _ in range(count)
        )
    except UnicodeDecodeError as exc:
        raise ProjectRequestError("project request metadata is not UTF-8") from exc
    if position != len(data):
        raise ProjectRequestError("project request has trailing data")
    request = ProjectRequest(package, entry, units, header_exports)
    # Re-encoding validates canonical paths, ordering, entry membership, and
    # non-empty fields without maintaining a second validation definition.
    if encode_project_request(request) != data:
        raise ProjectRequestError("project request is not canonical")
    return request


def request_from_sources(
    package: str,
    entry: str,
    units: Iterable[ProjectRequestUnit],
) -> ProjectRequest:
    return ProjectRequest(package, entry, tuple(units))


def encode_loaded_project_request(
    project: object, *, header_exports: frozenset[str] | None = None,
) -> bytes:
    """Encode a loaded project's paths and bytes without inspecting source text."""

    manifest = project.manifest
    root = manifest.root.resolve()
    units = tuple(
        ProjectRequestUnit(
            unit.path.resolve().relative_to(root).as_posix(),
            unit.path.read_bytes(),
        )
        for unit in sorted(project.units, key=lambda candidate: candidate.path.resolve())
    )
    entry = manifest.entry_path.resolve().relative_to(root).as_posix()
    return encode_project_request(ProjectRequest(
        manifest.name, entry, units,
        tuple(sorted(header_exports)) if header_exports is not None else None,
    ))
