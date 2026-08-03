from __future__ import annotations

from dataclasses import dataclass
import dataclasses
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
    end_column: Optional[int] = None


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: Optional[Path] = None
    line: Optional[int] = None
    column: Optional[int] = None
    source_line: Optional[str] = None
    notes: tuple[DiagnosticNote, ...] = ()
    end_column: Optional[int] = None

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
                width=max(1,(self.end_column or self.column+1)-self.column)
                lines.append(f"  | {' ' * max(self.column - 1, 0)}{'^' * width}")
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
                    width=max(1,(note.end_column or note.column+1)-note.column)
                    lines.append(f"  | {' ' * max(note.column - 1, 0)}{'^' * width}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        def path_text(value):return str(value) if value is not None else None
        return {
            "severity":"error","code":self.code,"message":self.message,
            "path":path_text(self.path),"line":self.line,"column":self.column,"end_column":self.end_column,
            "source_line":self.source_line,
            "notes":[{
                **{field.name:getattr(note,field.name) for field in dataclasses.fields(note) if field.name!='path'},
                "path":path_text(note.path),
            } for note in self.notes],
        }


def diagnostic_from_exception(exc: Exception, path: Path, source: str) -> Diagnostic:
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
        )
    if hasattr(exc, "code") and hasattr(exc, "message"):
        rows = source.splitlines()
        span = getattr(exc, "span", None)
        line = getattr(span, "line", None)
        column = getattr(span, "column", None)
        end_column = getattr(span, "end_column", None)
        source_line = rows[line - 1] if line is not None and 1 <= line <= len(rows) else None
        diagnostic_path = Path(span.source_name) if span is not None and getattr(span, "source_name", None) else path
        notes = []
        for note in getattr(exc, "notes", ()):
            note_span = getattr(note, "span", None)
            note_line = getattr(note_span, "line", None)
            note_column = getattr(note_span, "column", None)
            note_end_column = getattr(note_span, "end_column", None)
            note_path = Path(note_span.source_name) if note_span is not None and getattr(note_span, "source_name", None) else diagnostic_path
            note_rows = rows
            if note_path != diagnostic_path and note_path.is_file():
                note_rows = note_path.read_text().splitlines()
            note_source = note_rows[note_line - 1] if note_line is not None and 1 <= note_line <= len(note_rows) else None
            notes.append(DiagnosticNote(note.message, note_line, note_column, note_source, note_path, note_end_column))
        return Diagnostic(exc.code, exc.message, diagnostic_path, line, column, source_line, tuple(notes), end_column)
    return Diagnostic("M0000", str(exc), path)


def render_exception(exc: Exception, path: Path, source: str) -> str:
    return diagnostic_from_exception(exc,path,source).render()
