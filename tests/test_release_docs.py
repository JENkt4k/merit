import tomllib
from pathlib import Path
import re

from merit import __version__


ROOT=Path(__file__).resolve().parents[1]


def test_release_documents_exist_and_name_the_active_target():
    for name in ('STATUS.md','LIMITATIONS.md','ROADMAP.md','ALPHA_READINESS.md'):
        text=(ROOT/name).read_text()
        assert 'v0.1.0-alpha.2' in text


def test_status_records_the_alpha2_release_and_self_hosting_frontier():
    status=(ROOT/'STATUS.md').read_text()
    assert 'Alpha.2 is released' in status
    assert 'M1-M10 are closed' in status
    assert 'POST_ALPHA2_CLEANUP.md' in status
    assert 'SELF_HOSTING.md' in status
    assert 'independent semantic' in status
    assert 'diagnostic reference oracle' in status
    assert 'No known semantic correctness blocker remains undocumented' in status


def test_package_version_matches_the_alpha_release():
    metadata=tomllib.loads((ROOT/'pyproject.toml').read_text())
    assert metadata['project']['version'] == __version__ == '0.1.0a2'


def test_roadmap_keeps_deferred_work_outside_the_alpha_gate():
    roadmap=(ROOT/'ROADMAP.md').read_text()
    gate,post_alpha=roadmap.split('## After the first alpha',1)
    assert 'does not require stored references' in gate
    for deferred in ('Async','concurrency','networking','LLVM','registry'):
        assert deferred.lower() in post_alpha.lower()
    assert 'hosted CI' in post_alpha


def test_bootstrap_authority_and_pipeline_boundaries_are_explicit():
    specification=(ROOT/'spec/BOOTSTRAP.md').read_text()
    for stage in ('reference', 'bootstrap compiler', 'trusted compiler', 'self-hosted'):
        assert stage in specification.lower()
    pipeline=('Source','Lexer','Tokens','Concrete Syntax Tree','AST','HIR','Semantic analysis','Ownership / contracts / capabilities','MIR','Deterministic C lowering','Native compilation')
    positions=[specification.index(stage) for stage in pipeline]
    assert positions == sorted(positions)
    assert 'parser index prototype, not the CST' in specification


def test_bootstrap_status_reports_required_quality_dimensions():
    status=(ROOT/'BOOTSTRAP_STATUS.md').read_text()
    for metric in ('Total tests passing','Compile-pass tests','Compile-fail tests','Acceptance projects','Lexer differential cases','Parser differential cases','AST differential cases','HIR differential cases','Bootstrap/reference parity','Reference compiler source','Merit-native compiler source','Generated C size','Known semantic blockers'):
        assert metric in status
    assert 'Trusted for the documented Alpha.1 production surface' in status
    assert 'not self-hosted' in status


def test_alpha2_release_boundary_keeps_oracle_and_self_hosting_distinct():
    limitations=(ROOT/'LIMITATIONS.md').read_text()
    roadmap=(ROOT/'ROADMAP.md').read_text()
    assert 'replacement compiler by default' in limitations
    assert 'independent oracle' in limitations
    assert 'Self-hosting' in roadmap
    assert 'post-alpha.2' in roadmap.lower()


def test_post_alpha2_cleanup_is_bounded_and_preserves_encodings():
    cleanup=(ROOT/'POST_ALPHA2_CLEANUP.md').read_text()
    for inventory_id in range(1,11):
        assert f'N{inventory_id}' in cleanup
    assert 'Do not renumber' in cleanup
    assert 'language semantics' in cleanup
    assert 'Python and Merit bootstrap mappings have parity evidence' in cleanup
    assert 'ALPHA3_CLOSURE.md' in cleanup


def test_self_hosting_ledger_locks_complete_merit_source_inventory():
    ledger=(ROOT/'SELF_HOSTING.md').read_text(encoding='utf-8')
    inventory=ledger.split('## Complete Merit source inventory',1)[1].split(
        '## Current special-stage seam audit',1
    )[0]
    documented=set(re.findall(r'`([a-z0-9_]+\.mrt)`',inventory))
    project_root=ROOT/'examples/projects/bootstrap_lexer'
    source_root=project_root/'src'
    actual={path.relative_to(source_root).as_posix() for path in source_root.rglob('*.mrt')}
    manifest=tomllib.loads((project_root/'Merit.toml').read_text(encoding='utf-8'))
    assert manifest['package']['sources'] == ['src/**/*.mrt']
    assert documented == actual
    assert len(actual) == 46


def test_self_hosting_ledger_defines_public_interface_seams_and_evidence():
    ledger=(ROOT/'SELF_HOSTING.md').read_text(encoding='utf-8')
    for requirement in (
        'merit-project build',
        '--compiler-path',
        'Current special-stage seam audit',
        'Python remains an independent',
        'SH0 — Inventory and contract',
        'SH6 — Cross-platform qualification and handoff',
        'Machine-readable evidence',
        'Completion evidence matrix',
        'Ubuntu and native-Windows',
    ):
        assert requirement in ledger
    assert 'does not authorize Alpha.3 language features' in ledger
