from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lark.exceptions import UnexpectedInput


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: Optional[Path] = None
    line: Optional[int] = None
    column: Optional[int] = None
    source_line: Optional[str] = None

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
    return Diagnostic("M0000", str(exc), path).render()
