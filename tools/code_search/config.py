from __future__ import annotations

from pathlib import Path

# tools/code_search/config.py -> repo root is two directories above code_search.
REPO_ROOT = Path(__file__).resolve().parents[2]

INDEX_DIR = REPO_ROOT / ".merit-index"
TABLE_NAME = "code_chunks"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Merit source is .mrt. Keep .merit only as a harmless legacy/experimental alias.
CODE_EXTENSIONS = {
    ".mrt",
    ".merit",
    ".py",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".hpp",
    ".hh",
    ".hxx",
    ".rs",
}

DOC_EXTENSIONS = {
    ".md",
    ".rst",
    ".txt",
}

CONFIG_EXTENSIONS = {
    ".toml",
    ".yaml",
    ".yml",
    ".json",
}

INCLUDE_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS | CONFIG_EXTENSIONS

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".merit-index",
    "__pycache__",
    "node_modules",
    "target",
    "build",
    "dist",
}

# Line-based chunking is intentionally simple for v1. AST-aware chunking can
# replace this later without changing the MCP/search API.
CHUNK_LINES = 60 #120
CHUNK_OVERLAP = 10 #20

# Embedding several chunks at once is substantially faster than one-by-one.
EMBED_BATCH_SIZE = 64

MAX_SEARCH_RESULTS = 5
MAX_RESULT_CHARS = 6000
MAX_TOTAL_RESULT_CHARS = 18000
MAX_FILE_CHARS = 24000
