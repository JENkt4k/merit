# Owned replacement parity boundary

This test-local note records the semantic boundary exercised by `test_bootstrap_mir_owned_replace_gate.py` and `test_bootstrap_mir_source_ownership_gate.py`.

The native ownership event contract distinguishes replacement from a temporary local from replacement that consumes another owned source binding. For the latter, native Merit must preserve both target and source binding identities, mark the source moved, restore the target to live after destroying its old value, and prevent the consumed source from receiving later implicit cleanup.

The source-backed gate derives the source binding through native expression AST/HIR records rather than source-text inference, then carries that identity through ownership normalization, structured CFG lowering, instruction placement, interpreter execution, and generated native execution.
