import tomllib
from pathlib import Path

from merit import __version__


ROOT=Path(__file__).resolve().parents[1]


def test_release_documents_exist_and_name_the_active_target():
    for name in ('STATUS.md','LIMITATIONS.md','ROADMAP.md','ALPHA_READINESS.md'):
        text=(ROOT/name).read_text()
        assert 'v0.1.0-alpha.1' in text


def test_status_records_the_completed_local_alpha_gate():
    status=(ROOT/'STATUS.md').read_text()
    assert 'local release gate is complete' in status
    assert 'ledger application' in status
    assert 'arbitrary-precision' in status
    assert 'No known semantic correctness blocker remains undocumented' in status


def test_package_version_matches_the_alpha_release():
    metadata=tomllib.loads((ROOT/'pyproject.toml').read_text())
    assert metadata['project']['version'] == __version__ == '0.1.0a1'


def test_roadmap_keeps_deferred_work_outside_the_alpha_gate():
    roadmap=(ROOT/'ROADMAP.md').read_text()
    gate,post_alpha=roadmap.split('## After the first alpha',1)
    assert 'does not require stored references' in gate
    for deferred in ('Async','concurrency','networking','LLVM','registry'):
        assert deferred.lower() in post_alpha.lower()
    assert 'hosted CI' in post_alpha
