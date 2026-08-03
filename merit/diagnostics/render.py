from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lark.exceptions import UnexpectedInput


@dataclass(frozen=True)
class DiagnosticNote:
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    source_line: Optional[str] = None
    path: Optional[Path] = None


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: Optional[Path] = None
    line: Optional[int] = None
    column: Optional[int] = None
    source_line: Optional[str] = None
    notes: tuple[DiagnosticNote, ...] = ()

    def render(self) -> str:
        head = f"error[{self.code}]: {self.message}"
        if self.path is None:
            return head
        location = str(self.path)
        if self.line is not None:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"
        lines = [head, f" --> {location}"]
        if self.source_line is not None and self.line is not None:
            number = str(self.line)
            lines += ["  |", f"{number} | {self.source_line}"]
            if self.column is not None:
                lines.append(f"  | {' ' * max(self.column - 1, 0)}^")
        for note in self.notes:
            note_location = str(note.path or self.path)
            if note.line is not None:
                note_location += f":{note.line}"
                if note.column is not None:
                    note_location += f":{note.column}"
            lines += [f"note: {note.message}", f" --> {note_location}"]
            if note.source_line is not None and note.line is not None:
                number = str(note.line)
                lines += ["  |", f"{number} | {note.source_line}"]
                if note.column is not None:
                    lines.append(f"  | {' ' * max(note.column - 1, 0)}^")
        return "\n".join(lines)


def render_exception(exc: Exception, path: Path, source: str) -> str:
    if isinstance(exc, UnexpectedInput):
        line = getattr(exc, "line", None)
        column = getattr(exc, "column", None)
        source_line = None
        if line is not None:
            rows = source.splitlines()
            if 1 <= line <= len(rows):
                source_line = rows[line - 1]
        return Diagnostic(
            "M0002",
            "syntax error",
            path,
            line,
            column,
            source_line,
        ).render()
    if hasattr(exc, "code") and hasattr(exc, "message"):
        rows = source.splitlines()
        span = getattr(exc, "span", None)
        line = getattr(span, "line", None)
        column = getattr(span, "column", None)
        source_line = rows[line - 1] if line is not None and 1 <= line <= len(rows) else None
        diagnostic_path = Path(span.source_name) if span is not None and getattr(span, "source_name", None) else path
        notes = []
        for note in getattr(exc, "notes", ()):
            note_span = getattr(note, "span", None)
            note_line = getattr(note_span, "line", None)
            note_column = getattr(note_span, "column", None)
            note_source = rows[note_line - 1] if note_line is not None and 1 <= note_line <= len(rows) else None
            note_path = Path(note_span.source_name) if note_span is not None and getattr(note_span, "source_name", None) else diagnostic_path
            notes.append(DiagnosticNote(note.message, note_line, note_column, note_source, note_path))
        return Diagnostic(exc.code, exc.message, diagnostic_path, line, column, source_line, tuple(notes)).render()
    return Diagnostic("M0000", str(exc), path).render()
