from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest
from lark.exceptions import UnexpectedInput

from merit.bootstrap.native_frontend_driver import build_native_replacement_driver
from merit.bootstrap.resolved_source_function_bundle import decode_resolved_source_function_bundle
from merit.compiler import CompileError, parse
from merit.project.build import build
from merit.project.loader import load_project
from merit.project.replacement import ReplacementProjectError, build_replacement_project
from merit.project.replacement_prepare import prepare_replacement_artifacts


SOURCE = "module main\nfn main()->i32 { return 7; }\n"
MULTI_FUNCTION_SOURCE = (
    "module main\n"
    "fn helper()->i32 { return 6; }\n"
    "fn main()->i32 { return 7; }\n"
)
CAPABILITY_SOURCE = (
    "module main\n"
    "capability clock;\n"
    "fn main()->i32 { with capability clock { return 7; } }\n"
)
UNKNOWN_CAPABILITY_SOURCE = (
    "module main\n"
    "fn main()->i32 { with capability clock { return 7; } }\n"
)
ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Left, Right }\n"
    "fn main()->i32 { let flag:Choice=0; match (flag) { Left => { return 7; } Right => { } } return 8; }\n"
)
MULTI_ENUM_TYPED_SOURCE = (
    "module main\n"
    "enum OtherChoice { First, Second }\n"
    "enum Choice { Left, Right }\n"
    "fn main()->i32 { let flag:Choice=0; match (flag) { Left => { return 7; } Right => { } } return 8; }\n"
)
UNTYPED_MULTI_ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Left, Right }\n"
    "enum OtherChoice { First, Second }\n"
    "fn main()->i32 { let flag:i64=0; match (flag) { Left => { return 7; } Right => { } } return 8; }\n"
)
PAYLOAD_ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Left(i64), Right(i64) }\n"
    "fn main()->i32 { let flag:Choice=Left(1); match (flag) { Left(x) => { return 7; } Right(y) => { return 8; } } }\n"
)
CONTROL_FLOW_SOURCES = (
    (
        "if-else",
        "module main\nfn main()->i32 { if 2<3 { return 17; } else { return 18; } }\n",
        17,
        "",
    ),
    (
        "nested-early-return",
        "module main\nfn main()->i32 { if 1<2 { if 4>3 { return 19; } else { return 20; } } else { return 21; } }\n",
        19,
        "",
    ),
    (
        "loop-early-return",
        "module main\nfn main()->i32 { while 1<2 { if 3==3 { return 22; } else { return 23; } } return 24; }\n",
        22,
        "",
    ),
    (
        "skipped-loop",
        "module main\nfn main()->i32 { while 2<1 { return 25; } return 26; }\n",
        26,
        "",
    ),
    (
        "branch-loop-assignment",
        "module main\nfn main()->i32 { var x:i32=1; if 2<3 { x=x+4; } else { x=9; } while x<7 { x=x+1; } x+100; return x+20; }\n",
        27,
        "",
    ),
    (
        "loop-print",
        "module main\nfn main()->i32 { var x:i32=0; while x<3 { print(x); x=x+1; } return x; }\n",
        3,
        "0\n1\n2\n",
    ),
)
INVALID_CONTROL_FLOW_SOURCE = (
    "module main\nfn main()->i32 { if 1<2 { return 7; } else { return 8; }\n"
)
IMMUTABLE_ASSIGNMENT_SOURCE = (
    "module main\nfn main()->i32 { let x:i32=1; x=2; return x; }\n"
)


def _project(tmp_path: Path, source: str = SOURCE) -> Path:
    root = tmp_path / "native_driver_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "native_driver_project"\nentry = "src/main.mrt"\nsources = ["src/**/*.mrt"]\n\n'
        '[build]\nc_flags = ["-O2"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(source, encoding="utf-8")
    return root


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_reaches_replacement_executable_without_python_semantic_lowering(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    completed = subprocess.run(
        [str(driver.executable)],
        input=SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1
    assert len(bundle.encoded_snapshots) == 1

    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-driver")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_lowers_each_function_into_one_bundle_item(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    completed = subprocess.run(
        [str(driver.executable)],
        input=MULTI_FUNCTION_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 2
    assert len(bundle.encoded_snapshots) == 2

    root = _project(tmp_path, MULTI_FUNCTION_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 2

    artifact = build_replacement_project(project, root / "build" / "replacement-native-multifunction")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_closes_branch_loop_and_early_return_control_flow(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    for case_name, source, expected_status, expected_stdout in CONTROL_FLOW_SOURCES:
        root = _project(tmp_path / case_name, source)
        project = load_project(root / "Merit.toml")

        _, _, reference_executable = build(project, root / "build" / "reference")
        reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
        assert reference.returncode == expected_status
        assert reference.stdout == expected_stdout

        first = subprocess.run(
            [str(driver.executable)], input=source, text=True, capture_output=True, check=True
        )
        second = subprocess.run(
            [str(driver.executable)], input=source, text=True, capture_output=True, check=True
        )
        assert first.stdout == second.stdout
        bundle = decode_resolved_source_function_bundle(
            tuple(int(line) for line in first.stdout.splitlines())
        )
        assert len(bundle.functions) == 1

        prepared = prepare_replacement_artifacts(project, driver)
        assert len(prepared.snapshot_paths) == 1
        artifact = build_replacement_project(project, root / "build" / "replacement")
        replacement = subprocess.run(
            [str(artifact.executable)], text=True, capture_output=True
        )
        assert replacement.returncode == reference.returncode
        assert replacement.stdout == reference.stdout


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_rejects_malformed_control_flow_deterministically(tmp_path: Path) -> None:
    with pytest.raises(UnexpectedInput):
        parse(INVALID_CONTROL_FLOW_SOURCE)

    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run(
        [str(driver.executable)], input=INVALID_CONTROL_FLOW_SOURCE, text=True, capture_output=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=INVALID_CONTROL_FLOW_SOURCE, text=True, capture_output=True
    )
    assert first.returncode != 0
    assert first.stderr.startswith("replacement driver status ")
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )
    assert first.stderr.startswith("replacement driver status ")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_rejects_immutable_assignment_deterministically(tmp_path: Path) -> None:
    root = _project(tmp_path, IMMUTABLE_ASSIGNMENT_SOURCE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(CompileError, match="cannot assign to immutable"):
        build(project, root / "build" / "reference")

    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run(
        [str(driver.executable)], input=IMMUTABLE_ASSIGNMENT_SOURCE, text=True, capture_output=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=IMMUTABLE_ASSIGNMENT_SOURCE, text=True, capture_output=True
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_derives_capability_catalog_from_source(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    completed = subprocess.run(
        [str(driver.executable)],
        input=CAPABILITY_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1

    root = _project(tmp_path, CAPABILITY_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-capability")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_undeclared_capability(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path, UNKNOWN_CAPABILITY_SOURCE)
    project = load_project(root / "Merit.toml")

    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_derives_payload_free_enum_catalog_from_source(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    completed = subprocess.run(
        [str(driver.executable)],
        input=ENUM_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1

    root = _project(tmp_path, ENUM_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-enum")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_derives_match_enum_identity_from_declared_subject_type(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")

    completed = subprocess.run(
        [str(driver.executable)],
        input=MULTI_ENUM_TYPED_SOURCE,
        text=True,
        capture_output=True,
        check=True,
    )
    values = tuple(int(line) for line in completed.stdout.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 1

    root = _project(tmp_path, MULTI_ENUM_TYPED_SOURCE)
    project = load_project(root / "Merit.toml")
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1

    artifact = build_replacement_project(project, root / "build" / "replacement-native-typed-match")
    executed = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert executed.returncode == 7
    assert executed.stdout == ""


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_when_match_subject_type_is_not_an_enum(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path, UNTYPED_MULTI_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")

    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_payload_enum_lifecycle(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path, PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")

    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()
