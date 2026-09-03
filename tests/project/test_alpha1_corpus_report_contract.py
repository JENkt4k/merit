from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "alpha1_corpus_report.py"


def _load_report_module():
    specification = importlib.util.spec_from_file_location(
        "merit_alpha1_corpus_report", SCRIPT
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_alpha1_corpus_report_discovers_complete_epoch_reference_set() -> None:
    report = _load_report_module()
    expected = tuple(
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in sorted((ROOT / "tests").glob("test_epoch_*.py"))
    )
    assert report.REFERENCE_CORPUS == expected
    assert report.REFERENCE_CORPUS
    assert report.CONVERGENCE_CORPUS == (
        "tests/bootstrap/test_alpha1_corpus_convergence.py",
    )
