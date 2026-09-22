from __future__ import annotations

import os
from pathlib import Path

from merit.project.build import NATIVE_OBJECT_CACHE_ENV


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


# Test projects intentionally use isolated output directories. Share only the
# immutable, content-addressed host object cache; production builds retain their
# output-local default unless callers explicitly opt in through the same env var.
os.environ.setdefault(
    NATIVE_OBJECT_CACHE_ENV,
    str(REPOSITORY_ROOT / ".merit" / "test-native-object-cache"),
)
