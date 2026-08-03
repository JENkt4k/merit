# Verified Baseline

Export verification completed on 2026-07-30.

Commands:
```bash
python -m pip install -e . --no-build-isolation
python -m pytest -q
merit-project verify examples/projects/text_pipeline
merit-project verify examples/projects/binary_packet
merit-project verify examples/projects/generic_result
```

Results:
```text
50 passed
text_pipeline: verified 2 modules; output matches (26 bytes)
binary_packet: verified 2 modules; output matches (16 bytes)
generic_result: verified 1 modules; output matches (6 bytes)
```

Native compilation emitted unused-static-function warnings because the compact C backend currently emits the complete runtime helper set into each translation unit. These warnings do not affect correctness and are a useful future dead-runtime-elimination task.
