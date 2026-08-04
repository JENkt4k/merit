# Verified Baseline

Verification completed on 2026-08-04.

Commands:
```bash
python -m pip install -e ".[dev]" --no-build-isolation
python -m pytest -q
merit-project verify examples/projects/text_pipeline
merit-project verify examples/projects/binary_packet
merit-project verify examples/projects/generic_result
merit-project verify examples/projects/trait_bounds
merit-project verify examples/projects/generic_collections
merit-project verify examples/projects/borrowed_views
merit-project verify examples/projects/bootstrap_lexer
merit-project verify examples/projects/ledger_app
# filesystem_capabilities is verified from a temporary working directory
```

Results:
```text
354 passed
text_pipeline: verified 2 modules; output matches (26 bytes)
binary_packet: verified 2 modules; output matches (16 bytes)
generic_result: verified 1 modules; output matches (6 bytes)
trait_bounds: verified 1 modules; output matches (3 bytes)
generic_collections: verified 1 modules; output matches (38 bytes)
borrowed_views: verified 2 modules; output matches (4 bytes)
bootstrap_lexer: verified 2 modules; output matches (112 bytes)
filesystem_capabilities: verified 1 modules; output matches (13 bytes)
ledger_app: verified 5 modules; output matches (26 bytes)
```

The full gate verifies interpreter/native equivalence for all nine acceptance projects, including the Merit-native bootstrap lexer, deterministic filesystem I/O confined to temporary directories, and the ledger shared-library ABI tests.
