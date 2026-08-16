from pathlib import Path
import shutil
import subprocess

import pytest

from merit.bootstrap.replacement_build import (
    ReplacementBuildArtifact,
    ReplacementBuildError,
    build_replacement_artifact,
    compile_replacement_artifact,
)
from merit.bootstrap.resolved_source_function_snapshot import (
    ResolvedSourceFunctionSnapshotError,
)


def test_replacement_build_rejects_non_native_snapshot() -> None:
    with pytest.raises(ResolvedSourceFunctionSnapshotError, match="invalid magic"):
        build_replacement_artifact(
            source="module demo\n",
            module_name="demo",
            snapshot_values=(0, 1, 2),
            capability_names={},
        )


def test_replacement_artifact_compiles_emitted_c_without_semantic_relowering(tmp_path: Path) -> None:
    cc = next((candidate for candidate in ("cc", "gcc", "clang") if shutil.which(candidate)), None)
    if cc is None:
        pytest.skip("system C compiler is unavailable")

    # The compilation half of the production boundary accepts only already-emitted
    # canonical C plus an optional foreign harness; it has no source/HIR inputs.
    artifact = ReplacementBuildArtifact(
        module=None,  # type: ignore[arg-type] -- compile step deliberately ignores semantic objects
        c_source="long long merit_replacement_probe(void) { return 42; }\n",
    )
    c_path, executable = compile_replacement_artifact(
        artifact,
        tmp_path / "replacement-probe",
        cc=cc,
        main_c=(
            '#include <stdio.h>\n'
            'int main(void) { printf("%lld\\n", merit_replacement_probe()); return 0; }'
        ),
    )
    assert c_path.read_text(encoding="utf-8").startswith("long long merit_replacement_probe")
    completed = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert completed.stdout == "42\n"


def test_replacement_compile_fails_closed_without_compiler(tmp_path: Path) -> None:
    artifact = ReplacementBuildArtifact(module=None, c_source="int x;\n")  # type: ignore[arg-type]
    with pytest.raises(ReplacementBuildError):
        compile_replacement_artifact(artifact, tmp_path / "x", cc="definitely-not-a-c-compiler")
