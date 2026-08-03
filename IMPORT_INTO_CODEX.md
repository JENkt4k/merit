# Importing this export into Codex

1. Extract the archive into a new workspace or repository.
2. Open the extracted directory as the Codex working directory.
3. Ask Codex to read `AGENTS.md` and `CODEX_HANDOFF.md` before changing files.
4. Run:
   ```bash
   ./scripts/bootstrap.sh
   ./scripts/test.sh
   ```
5. Continue with the subsystem in `NEXT_WORK.md`.

Suggested opening instruction:

> Read AGENTS.md, CODEX_HANDOFF.md, NEXT_WORK.md, ARCHITECTURE.md, EPOCH-III.md, and the ownership/numerics specs. Establish the 50-test baseline, then implement the Traits and Generic Collections subsystem. Preserve interpreter/native equivalence and commit in coherent stages. Do not mark the checkpoint complete until every acceptance gate in NEXT_WORK.md passes.
