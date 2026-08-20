from pathlib import Path


def test_resolved_source_pipeline_uses_per_match_identity_resolver():
    root = Path(__file__).resolve().parents[2]
    pipeline = (root / "examples/projects/bootstrap_lexer/src/mir_resolved_source_function_pipeline.mrt").read_text()
    semantics = (root / "examples/projects/bootstrap_lexer/src/statement_semantics.mrt").read_text()

    assert "resolve_match_arms_by_identity" in semantics
    assert "MatchEnumIdentity" in semantics

    # The production source-function pipeline must no longer reject a function
    # merely because it contains more than one match statement.
    assert "if (match_statement_count != 1)" not in pipeline

    # Negative/derived identity mode must feed the per-match resolver. The
    # scalar resolver remains only as a compatibility path for explicit ids.
    assert "resolve_match_arms_by_identity(" in pipeline
    assert "Vec<MatchEnumIdentity>" in pipeline
