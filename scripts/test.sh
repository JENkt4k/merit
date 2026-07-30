#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
merit-project verify examples/projects/text_pipeline
merit-project verify examples/projects/binary_packet
merit-project verify examples/projects/generic_result
merit-project verify examples/projects/trait_bounds
