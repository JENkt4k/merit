from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server import MCPServer

mcp = MCPServer("Merit Code Search")

try:
    from .config import REPO_ROOT
    from .search import get_search_engine
except ImportError:
    from config import REPO_ROOT
    from search import get_search_engine


# mcp = FastMCP("Merit Code Search")


# def _serialize_results(results: list) -> list[dict[str, Any]]:
#     return [result.as_dict() for result in results]
def _serialize_results(
    results: list,
    max_results: int = 5,
    max_result_chars: int = 6000,
    max_total_chars: int = 18000,
) -> list[dict[str, Any]]:
    output = []
    total_chars = 0

    for result in results[:max_results]:
        item = result.as_dict()

        text = item.get("text", "")

        remaining = max_total_chars - total_chars
        if remaining <= 0:
            break

        allowed = min(max_result_chars, remaining)

        if len(text) > allowed:
            text = text[:allowed] + "\n...[truncated]"

        item["text"] = text

        output.append(item)
        total_chars += len(text)

    return output


def _safe_repo_path(path: str) -> Path:
    requested = Path(path)

    if requested.is_absolute():
        candidate = requested.resolve()
    else:
        candidate = (REPO_ROOT / requested).resolve()

    repo_root = REPO_ROOT.resolve()

    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(
            f"Path must stay inside the repository: {path}"
        ) from exc

    return candidate


@mcp.tool()
def search_code(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search source code with semantic vector search plus BM25 lexical ranking."""
    return _serialize_results(
        get_search_engine().search_code(query=query, limit=limit)
    )


@mcp.tool()
def search_docs(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search project documentation with semantic and lexical retrieval."""
    return _serialize_results(
        get_search_engine().search_docs(query=query, limit=limit)
    )


@mcp.tool()
def find_text(
    text: str,
    limit: int = 50,
    regex: bool = False,
    case_sensitive: bool = False,
) -> list[dict[str, Any]]:
    """Find literal or regex text in repository files, with nearby line context."""
    return _serialize_results(
        get_search_engine().find_text(
            text=text,
            limit=limit,
            regex=regex,
            case_sensitive=case_sensitive,
        )
    )


@mcp.tool()
def find_symbol(symbol: str, limit: int = 50) -> list[dict[str, Any]]:
    """Find likely declarations of a source-code symbol."""
    return _serialize_results(
        get_search_engine().find_symbol(symbol=symbol, limit=limit)
    )


@mcp.tool()
def find_references(symbol: str, limit: int = 100) -> list[dict[str, Any]]:
    """Find exact lexical references to a source-code symbol."""
    return _serialize_results(
        get_search_engine().find_references(symbol=symbol, limit=limit)
    )


@mcp.tool()
def get_file(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> dict[str, Any]:
    """Read a UTF-8 text file inside the repository, optionally by line range."""
    file_path = _safe_repo_path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    start = max(1, int(start_line))

    if end_line is None:
        end = len(lines)
    else:
        end = min(len(lines), max(start, int(end_line)))

    selected = "\n".join(lines[start - 1 : end])

    return {
        "path": file_path.relative_to(REPO_ROOT.resolve()).as_posix(),
        "start_line": start,
        "end_line": end,
        "total_lines": len(lines),
        "text": selected,
    }


if __name__ == "__main__":
    # Continue launches this process and communicates with it over stdio.
    mcp.run(transport="stdio")
