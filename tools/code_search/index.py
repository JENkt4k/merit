from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Iterable, Iterator

import lancedb
from sentence_transformers import SentenceTransformer

try:
    from .config import (
        CHUNK_LINES,
        CHUNK_OVERLAP,
        CODE_EXTENSIONS,
        DOC_EXTENSIONS,
        EMBED_BATCH_SIZE,
        EMBEDDING_MODEL,
        EXCLUDE_DIRS,
        INCLUDE_EXTENSIONS,
        INDEX_DIR,
        REPO_ROOT,
        TABLE_NAME,
    )
except ImportError:
    from config import (
        CHUNK_LINES,
        CHUNK_OVERLAP,
        CODE_EXTENSIONS,
        DOC_EXTENSIONS,
        EMBED_BATCH_SIZE,
        EMBEDDING_MODEL,
        EXCLUDE_DIRS,
        INCLUDE_EXTENSIONS,
        INDEX_DIR,
        REPO_ROOT,
        TABLE_NAME,
    )


def language_from_path(path: str | Path) -> str | None:
    extension = Path(path).suffix.lower()

    mapping = {
        ".mrt": "merit",
        ".merit": "merit",
        ".py": "python",
        ".c": "c",
        ".h": "c",
        ".cc": "cpp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".rs": "rust",
        ".md": "markdown",
        ".rst": "rst",
        ".txt": "text",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }

    return mapping.get(extension)


def kind_from_path(path: str | Path) -> str:
    extension = Path(path).suffix.lower()

    if extension in CODE_EXTENSIONS:
        return "code"
    if extension in DOC_EXTENSIONS:
        return "docs"
    return "config"


def iter_repository_files(root: Path = REPO_ROOT) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(part in EXCLUDE_DIRS for part in relative.parts):
            continue

        if path.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue

        yield path


def chunk_text(
    text: str,
    chunk_lines: int = CHUNK_LINES,
    overlap: int = CHUNK_OVERLAP,
) -> Iterator[tuple[int, int, str]]:
    if chunk_lines <= 0:
        raise ValueError("chunk_lines must be greater than zero")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_lines:
        raise ValueError("overlap must be smaller than chunk_lines")

    lines = text.splitlines()

    if not lines:
        return

    step = chunk_lines - overlap

    for start_index in range(0, len(lines), step):
        end_index = min(start_index + chunk_lines, len(lines))
        chunk = "\n".join(lines[start_index:end_index]).strip()

        if chunk:
            # Convert zero-based indexes to inclusive one-based line numbers.
            yield start_index + 1, end_index, chunk

        if end_index >= len(lines):
            break


def make_chunk_id(path: str, start_line: int, end_line: int, text: str) -> str:
    payload = f"{path}\0{start_line}\0{end_line}\0{text}".encode(
        "utf-8",
        errors="replace",
    )
    return hashlib.sha256(payload).hexdigest()


def collect_chunks(root: Path = REPO_ROOT) -> list[dict]:
    rows: list[dict] = []

    for path in iter_repository_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"Skipping unreadable file {path}: {exc}")
            continue

        relative_path = path.relative_to(root).as_posix()
        extension = path.suffix.lower()
        language = language_from_path(relative_path)
        kind = kind_from_path(relative_path)

        for start_line, end_line, chunk in chunk_text(text):
            rows.append(
                {
                    "id": make_chunk_id(
                        relative_path,
                        start_line,
                        end_line,
                        chunk,
                    ),
                    "path": relative_path,
                    "extension": extension,
                    "language": language or "unknown",
                    "kind": kind,
                    "start_line": start_line,
                    "end_line": end_line,
                    "text": chunk,
                }
            )

    return rows


def embed_chunks(
    rows: list[dict],
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = EMBED_BATCH_SIZE,
) -> list[dict]:
    if not rows:
        return rows

    model = SentenceTransformer(model_name)

    texts = [
        # Include the path in the embedding input because filenames and
        # directories frequently contain useful architectural terms.
        f"{row['path']}\n{row['text']}"
        for row in rows
    ]

    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    for row, vector in zip(rows, vectors, strict=True):
        row["vector"] = vector.astype("float32").tolist()

    return rows


def build_index(
    root: Path = REPO_ROOT,
    index_dir: Path = INDEX_DIR,
    model_name: str = EMBEDDING_MODEL,
) -> int:
    print(f"Repository: {root}")
    print(f"Index:      {index_dir}")
    print(f"Embedding:  {model_name}")

    rows = collect_chunks(root)

    if not rows:
        raise RuntimeError(
            "No indexable files were found. "
            "Check INCLUDE_EXTENSIONS and REPO_ROOT in config.py."
        )

    print(f"Collected {len(rows):,} chunks.")

    embed_chunks(rows, model_name=model_name)

    index_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(index_dir))

    # A complete rebuild is preferable for v1: deterministic, simple, and it
    # guarantees deleted/renamed files cannot leave stale chunks behind.
    db.create_table(
        TABLE_NAME,
        data=rows,
        mode="overwrite",
    )

    print(f"Wrote {len(rows):,} chunks to LanceDB table '{TABLE_NAME}'.")
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the local Merit code-search vector index."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to index.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=INDEX_DIR,
        help="LanceDB directory.",
    )
    parser.add_argument(
        "--model",
        default=EMBEDDING_MODEL,
        help="Sentence Transformers embedding model.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = args.repo.resolve()
    index_dir = args.index.resolve()

    if not root.is_dir():
        raise SystemExit(f"Repository directory does not exist: {root}")

    build_index(
        root=root,
        index_dir=index_dir,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
