from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import lancedb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

try:
    from .config import (
        CODE_EXTENSIONS,
        DOC_EXTENSIONS,
        EMBEDDING_MODEL,
        EXCLUDE_DIRS,
        INCLUDE_EXTENSIONS,
        INDEX_DIR,
        REPO_ROOT,
        TABLE_NAME,
    )
except ImportError:
    from config import (
        CODE_EXTENSIONS,
        DOC_EXTENSIONS,
        EMBEDDING_MODEL,
        EXCLUDE_DIRS,
        INCLUDE_EXTENSIONS,
        INDEX_DIR,
        REPO_ROOT,
        TABLE_NAME,
    )

DEFAULT_LIMIT = 10
MAX_LIMIT = 100

SEMANTIC_CANDIDATE_MULTIPLIER = 4
LEXICAL_CANDIDATE_MULTIPLIER = 4

SEMANTIC_WEIGHT = 0.50
LEXICAL_WEIGHT = 0.35
PATH_WEIGHT = 0.15


@dataclass(frozen=True)
class SearchResult:
    path: str
    start_line: int
    end_line: int
    text: str
    score: float
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    path_score: float = 0.0
    language: str | None = None
    kind: str | None = None

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "text": self.text,
            "score": round(self.score, 6),
            "semantic_score": round(self.semantic_score, 6),
            "lexical_score": round(self.lexical_score, 6),
            "path_score": round(self.path_score, 6),
            "language": self.language,
            "kind": self.kind,
        }


class CodeSearch:
    """Local hybrid repository search for Merit."""

    def __init__(
        self,
        index_dir: Path | str = INDEX_DIR,
        embedding_model: str = EMBEDDING_MODEL,
    ) -> None:
        self.index_dir = Path(index_dir)
        self.embedding_model_name = embedding_model

        self._db = None
        self._table = None
        self._model: SentenceTransformer | None = None

        self._documents: list[dict] = []
        self._tokenized_documents: list[list[str]] = []
        self._bm25: BM25Okapi | None = None

    def initialize(self) -> None:
        if not self.index_dir.exists():
            raise RuntimeError(
                f"Code-search index does not exist: {self.index_dir}\n"
                "Run tools/code_search/index.py first."
            )

        self._db = lancedb.connect(str(self.index_dir))

        # table_names() remains broadly compatible across LanceDB versions.
        table_names = set(self._db.table_names())
        if TABLE_NAME not in table_names:
            raise RuntimeError(
                f"LanceDB table '{TABLE_NAME}' was not found.\n"
                "Run tools/code_search/index.py first."
            )

        self._table = self._db.open_table(TABLE_NAME)
        self._load_documents()
        self._build_bm25()

    def _ensure_initialized(self) -> None:
        if self._table is None:
            self.initialize()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.embedding_model_name)
        return self._model

    def _load_documents(self) -> None:
        assert self._table is not None

        rows = self._table.to_arrow().to_pylist()

        self._documents = []

        for row in rows:
            self._documents.append(
                {
                    "id": row.get("id"),
                    "path": str(row.get("path", "")),
                    "extension": str(row.get("extension", "")),
                    "start_line": int(row.get("start_line", 0)),
                    "end_line": int(row.get("end_line", 0)),
                    "text": str(row.get("text", "")),
                    "language": row.get("language"),
                    "kind": row.get("kind"),
                }
            )

    def _build_bm25(self) -> None:
        self._tokenized_documents = [
            tokenize_for_code(f"{doc['path']} {doc['text']}")
            for doc in self._documents
        ]

        self._bm25 = (
            BM25Okapi(self._tokenized_documents)
            if self._tokenized_documents
            else None
        )

    def search_code(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
    ) -> list[SearchResult]:
        return self.hybrid_search(
            query=query,
            limit=limit,
            extensions=CODE_EXTENSIONS,
        )

    def search_docs(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
    ) -> list[SearchResult]:
        return self.hybrid_search(
            query=query,
            limit=limit,
            extensions=DOC_EXTENSIONS,
        )

    def hybrid_search(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        extensions: set[str] | None = None,
    ) -> list[SearchResult]:
        query = query.strip()
        limit = normalize_limit(limit)

        if not query:
            return []

        self._ensure_initialized()

        candidate_limit = max(
            limit
            * max(
                SEMANTIC_CANDIDATE_MULTIPLIER,
                LEXICAL_CANDIDATE_MULTIPLIER,
            ),
            20,
        )

        semantic_results = self.semantic_search(
            query=query,
            limit=candidate_limit,
            extensions=extensions,
        )
        lexical_results = self.lexical_search(
            query=query,
            limit=candidate_limit,
            extensions=extensions,
        )

        merged: dict[tuple[str, int, int], dict] = {}

        for result in semantic_results:
            merged[result_key(result)] = {
                "path": result.path,
                "start_line": result.start_line,
                "end_line": result.end_line,
                "text": result.text,
                "language": result.language,
                "kind": result.kind,
                "semantic_score": result.semantic_score,
                "lexical_score": 0.0,
            }

        for result in lexical_results:
            key = result_key(result)
            if key not in merged:
                merged[key] = {
                    "path": result.path,
                    "start_line": result.start_line,
                    "end_line": result.end_line,
                    "text": result.text,
                    "language": result.language,
                    "kind": result.kind,
                    "semantic_score": 0.0,
                    "lexical_score": result.lexical_score,
                }
            else:
                merged[key]["lexical_score"] = result.lexical_score

        results: list[SearchResult] = []

        for item in merged.values():
            path_score = calculate_path_score(query, item["path"])
            score = (
                SEMANTIC_WEIGHT * item["semantic_score"]
                + LEXICAL_WEIGHT * item["lexical_score"]
                + PATH_WEIGHT * path_score
            )

            results.append(
                SearchResult(
                    path=item["path"],
                    start_line=item["start_line"],
                    end_line=item["end_line"],
                    text=item["text"],
                    language=item["language"],
                    kind=item["kind"],
                    score=score,
                    semantic_score=item["semantic_score"],
                    lexical_score=item["lexical_score"],
                    path_score=path_score,
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                result.semantic_score,
                result.lexical_score,
            ),
            reverse=True,
        )
        return results[:limit]

    def semantic_search(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        extensions: set[str] | None = None,
    ) -> list[SearchResult]:
        self._ensure_initialized()
        assert self._table is not None

        limit = normalize_limit(limit)
        query_vector = self._get_model().encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32").tolist()

        # Filtering is done after vector search for maximum compatibility with
        # simple LanceDB schemas, so request extra candidates.
        search_limit = max(limit * 4, 40)

        items = (
            self._table.search(query_vector)
            .distance_type("cosine")
            .limit(search_limit)
            .to_list()
        )

        results: list[SearchResult] = []

        for item in items:
            path = str(item.get("path", ""))
            if extensions and Path(path).suffix.lower() not in extensions:
                continue

            distance = float(item.get("_distance", 2.0))

            # Cosine distance is [0, 2]. Map it to [0, 1], where 1 is best.
            semantic_score = max(0.0, min(1.0, 1.0 - distance / 2.0))

            results.append(
                SearchResult(
                    path=path,
                    start_line=int(item.get("start_line", 0)),
                    end_line=int(item.get("end_line", 0)),
                    text=str(item.get("text", "")),
                    language=item.get("language"),
                    kind=item.get("kind"),
                    score=semantic_score,
                    semantic_score=semantic_score,
                )
            )

            if len(results) >= limit:
                break

        return results

    def lexical_search(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        extensions: set[str] | None = None,
    ) -> list[SearchResult]:
        self._ensure_initialized()
        limit = normalize_limit(limit)

        if self._bm25 is None:
            return []

        query_tokens = tokenize_for_code(query)
        if not query_tokens:
            return []

        raw_scores = self._bm25.get_scores(query_tokens)
        candidates: list[tuple[int, float]] = []

        for index, raw_score in enumerate(raw_scores):
            score = float(raw_score)
            if score <= 0.0:
                continue

            document = self._documents[index]
            path = document["path"]

            if extensions and Path(path).suffix.lower() not in extensions:
                continue

            candidates.append((index, score))

        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[:limit]

        if not candidates:
            return []

        max_score = max(score for _, score in candidates) or 1.0

        return [
            SearchResult(
                path=self._documents[index]["path"],
                start_line=self._documents[index]["start_line"],
                end_line=self._documents[index]["end_line"],
                text=self._documents[index]["text"],
                language=self._documents[index].get("language"),
                kind=self._documents[index].get("kind"),
                score=raw_score / max_score,
                lexical_score=raw_score / max_score,
            )
            for index, raw_score in candidates
        ]

    def find_text(
        self,
        text: str,
        limit: int = 50,
        regex: bool = False,
        case_sensitive: bool = False,
        extensions: set[str] | None = None,
    ) -> list[SearchResult]:
        query = text.strip()
        limit = normalize_limit(limit)

        if not query:
            return []

        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            pattern = re.compile(query if regex else re.escape(query), flags)
        except re.error as exc:
            raise ValueError(f"Invalid regular expression: {exc}") from exc

        results: list[SearchResult] = []

        for file_path in iter_repository_files(
            root=REPO_ROOT,
            extensions=extensions,
        ):
            try:
                file_text = file_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            lines = file_text.splitlines()

            for line_number, line in enumerate(lines, start=1):
                if not pattern.search(line):
                    continue

                start_line = max(1, line_number - 3)
                end_line = min(len(lines), line_number + 3)
                relative_path = file_path.relative_to(REPO_ROOT).as_posix()

                results.append(
                    SearchResult(
                        path=relative_path,
                        start_line=start_line,
                        end_line=end_line,
                        text="\n".join(lines[start_line - 1 : end_line]),
                        score=1.0,
                        lexical_score=1.0,
                        language=language_from_path(relative_path),
                        kind=kind_from_path(relative_path),
                    )
                )

                if len(results) >= limit:
                    return results

        return results

    def find_symbol(
        self,
        symbol: str,
        limit: int = 50,
    ) -> list[SearchResult]:
        symbol = symbol.strip()
        if not symbol:
            return []

        escaped = re.escape(symbol)

        # Best-effort declaration search. Exact semantic symbol resolution can
        # be added later using the Merit parser/AST.
        patterns = [
            rf"\b(?:fn|func|function|def)\s+{escaped}\b",
            rf"\b(?:struct|class|trait|enum|union|type)\s+{escaped}\b",
            rf"\btypedef\b[^;\n]*\b{escaped}\b",
            rf"\b(?:const|static|let|var)\s+{escaped}\b",
        ]

        combined = "(?:" + "|".join(patterns) + ")"

        return self.find_text(
            combined,
            limit=limit,
            regex=True,
            case_sensitive=True,
            extensions=CODE_EXTENSIONS,
        )

    def find_references(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[SearchResult]:
        symbol = symbol.strip()
        if not symbol:
            return []

        return self.find_text(
            rf"\b{re.escape(symbol)}\b",
            limit=limit,
            regex=True,
            case_sensitive=True,
            extensions=CODE_EXTENSIONS,
        )


def normalize_limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def result_key(result: SearchResult) -> tuple[str, int, int]:
    return result.path, result.start_line, result.end_line


def tokenize_for_code(text: str) -> list[str]:
    tokens: list[str] = []

    raw_tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+",
        text,
    )

    for raw in raw_tokens:
        tokens.append(raw.lower())

        if "_" in raw:
            tokens.extend(
                part.lower()
                for part in raw.split("_")
                if part
            )

        camel_parts = re.findall(
            r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[0-9]+",
            raw,
        )
        if len(camel_parts) > 1:
            tokens.extend(part.lower() for part in camel_parts)

    return tokens


def calculate_path_score(query: str, path: str) -> float:
    query_tokens = set(tokenize_for_code(query))
    if not query_tokens:
        return 0.0

    path_tokens = set(tokenize_for_code(path))
    overlap = query_tokens & path_tokens

    return min(1.0, len(overlap) / len(query_tokens))


def language_from_path(path: str | Path) -> str | None:
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
    return mapping.get(Path(path).suffix.lower())


def kind_from_path(path: str | Path) -> str:
    extension = Path(path).suffix.lower()
    if extension in CODE_EXTENSIONS:
        return "code"
    if extension in DOC_EXTENSIONS:
        return "docs"
    return "config"


def iter_repository_files(
    root: Path,
    extensions: set[str] | None = None,
) -> Iterable[Path]:
    allowed_extensions = (
        extensions if extensions is not None else INCLUDE_EXTENSIONS
    )

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(part in EXCLUDE_DIRS for part in relative.parts):
            continue

        if path.suffix.lower() not in allowed_extensions:
            continue

        yield path


_default_search: CodeSearch | None = None


def get_search_engine() -> CodeSearch:
    global _default_search

    if _default_search is None:
        _default_search = CodeSearch()
        _default_search.initialize()

    return _default_search


def search_code(query: str, limit: int = DEFAULT_LIMIT) -> list[dict]:
    return [
        result.as_dict()
        for result in get_search_engine().search_code(query, limit)
    ]


def search_docs(query: str, limit: int = DEFAULT_LIMIT) -> list[dict]:
    return [
        result.as_dict()
        for result in get_search_engine().search_docs(query, limit)
    ]


def find_text(
    text: str,
    limit: int = 50,
    regex: bool = False,
    case_sensitive: bool = False,
) -> list[dict]:
    return [
        result.as_dict()
        for result in get_search_engine().find_text(
            text=text,
            limit=limit,
            regex=regex,
            case_sensitive=case_sensitive,
        )
    ]


def find_symbol(symbol: str, limit: int = 50) -> list[dict]:
    return [
        result.as_dict()
        for result in get_search_engine().find_symbol(symbol, limit)
    ]


def find_references(symbol: str, limit: int = 100) -> list[dict]:
    return [
        result.as_dict()
        for result in get_search_engine().find_references(symbol, limit)
    ]
