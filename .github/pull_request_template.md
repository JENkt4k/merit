## Summary

Describe the cohesive change and the Merit milestone or correctness issue it advances.

## Semantic impact

- [ ] No language-semantic change
- [ ] Specification updated for an intentional semantic change
- [ ] Interpreter and native behavior remain equivalent
- [ ] Ownership, cleanup, numerics, contracts, capabilities, and ABI behavior were considered where applicable

## Validation

- [ ] Focused tests pass
- [ ] `bash scripts/ci.sh` passes locally on Linux, or the hosted Linux gate is green
- [ ] `.\scripts\test-windows.ps1` passes when the change affects native builds, paths, filesystems, generated C, or subprocess behavior
- [ ] All nine acceptance projects pass
- [ ] Relevant generated C or serialized AST/HIR/MIR was inspected
- [ ] Compile-fail coverage was added or updated where applicable
- [ ] Documentation and status metrics are current

## Platform notes

Record the Python version, compiler, operating system, and any unavailable hosted runners. When hosted CI is unavailable, include the exact local gate command and result.

## Scope control

- [ ] No unrelated feature expansion or aesthetic refactoring
- [ ] No test was weakened or deleted to obtain a passing result
- [ ] Known limitations or follow-up work are documented
