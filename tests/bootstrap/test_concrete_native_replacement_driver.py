from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest
from lark.exceptions import UnexpectedInput

from merit.bootstrap.native_frontend_driver import build_native_replacement_driver
from merit.bootstrap.resolved_source_function_bundle import decode_resolved_source_function_bundle
from merit.bootstrap.resolved_source_function_snapshot import materialize_resolved_source_function_snapshot
from merit.compiler import CompileError, parse
from merit.project.build import build
from merit.project.loader import ProjectError, load_project
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
    "enum Choice { Left(i32), Right(i32) }\n"
    "fn main()->i32 { let flag:Choice=Left(7); match (flag) { Left(x) => { return x; } Right(y) => { return y; } } }\n"
)
OWNED_PAYLOAD_ENUM_SOURCE = (
    "module main\n"
    "enum Choice { Data(Buffer) }\n"
    "fn main()->i32 { return 7; }\n"
)
OWNED_DESTRUCTOR_PAYLOAD_ENUM_SOURCES = (
    (
        "implicit-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:31 }; let value:Envelope=Full(marker); return 0; }\n",
        "31\n",
    ),
    (
        "explicit-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:37 }; let value:Envelope=Full(marker); drop(value); return 0; }\n",
        "37\n",
    ),
    (
        "move-no-double-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:41 }; let first:Envelope=Full(marker); let second:Envelope=first; drop(second); return 0; }\n",
        "41\n",
    ),
    (
        "early-return-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:43 }; let value:Envelope=Full(marker); if 1<2 { return 0; } else { return 1; } }\n",
        "43\n",
    ),
    (
        "replace",
        "fn main()->i32 { let first_marker:Marker=Marker { number:47 }; var target:Envelope=Full(first_marker); let second_marker:Marker=Marker { number:53 }; let replacement:Envelope=Full(second_marker); replace(target,replacement); drop(target); return 0; }\n",
        "47\n53\n",
    ),
    (
        "match-payload-transfer",
        "fn main()->i32 { let marker:Marker=Marker { number:59 }; let value:Envelope=Spare(marker); match (value) { Full(payload) => { drop(payload); } Spare(payload) => { drop(payload); } } return 0; }\n",
        "59\n",
    ),
)
OWNED_DESTRUCTOR_PAYLOAD_ENUM_PREFIX = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "enum Envelope { Full(Marker), Spare(Marker) }\n"
)
UNSUPPORTED_MIXED_OWNED_PAYLOAD_ENUM_SOURCE = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "enum Envelope { Full(Marker), Count(i64) }\n"
    "fn main()->i32 { return 0; }\n"
)
RECURSIVE_OWNED_AGGREGATE_PREFIX = (
    "module main\n"
    "struct Marker { number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "struct Wrapper { marker:Marker; }\n"
    "struct Outer { wrapper:Wrapper; }\n"
    "enum Parcel { Wrapped(Outer), Spare(Outer) }\n"
)
RECURSIVE_OWNED_AGGREGATE_SOURCES = (
    (
        "implicit-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:101 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; return 0; }\n",
        "101\n",
    ),
    (
        "explicit-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:103 }; let wrapper:Wrapper=Wrapper { marker:marker }; drop(wrapper); return 0; }\n",
        "103\n",
    ),
    (
        "move-no-double-drop",
        "fn main()->i32 { let marker:Marker=Marker { number:107 }; let first:Wrapper=Wrapper { marker:marker }; let second:Wrapper=first; drop(second); return 0; }\n",
        "107\n",
    ),
    (
        "early-return-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:109 }; let wrapper:Wrapper=Wrapper { marker:marker }; if 1<2 { return 0; } else { return 1; } }\n",
        "109\n",
    ),
    (
        "replace",
        "fn main()->i32 { let first_marker:Marker=Marker { number:113 }; var target:Wrapper=Wrapper { marker:first_marker }; let second_marker:Marker=Marker { number:127 }; let replacement:Wrapper=Wrapper { marker:second_marker }; replace(target,replacement); drop(target); return 0; }\n",
        "113\n127\n",
    ),
    (
        "enum-match-transfer",
        "fn main()->i32 { let marker:Marker=Marker { number:131 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Spare(outer); match (parcel) { Wrapped(value) => { drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "131\n",
    ),
)
RECURSIVE_OWNED_AGGREGATE_CYCLE = (
    "module main\nstruct First { second:Second; }\nstruct Second { first:First; }\n"
    "fn main()->i32 { return 0; }\n"
)

MULTI_FIELD_OWNED_AGGREGATE_PREFIX = (
    "module main\n"
    "struct Marker { prefix:i64; number:i64; }\n"
    "destructor Marker { print(self.number); }\n"
    "struct Pair { left:Marker; code:i64; right:Marker; }\n"
    "enum Packet { Full(Pair), Spare(Pair) }\n"
)
MULTI_FIELD_OWNED_AGGREGATE_SOURCES = (
    (
        "implicit-cleanup",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:233 }; let right:Marker=Marker { prefix:2, number:239 }; let pair:Pair=Pair { left:left, code:3, right:right }; return 0; }\n",
        "233\n239\n",
    ),
    (
        "explicit-drop",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:241 }; let right:Marker=Marker { prefix:2, number:251 }; let pair:Pair=Pair { left:left, code:3, right:right }; drop(pair); return 0; }\n",
        "241\n251\n",
    ),
    (
        "move-no-double-drop",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:257 }; let right:Marker=Marker { prefix:2, number:263 }; let first:Pair=Pair { left:left, code:3, right:right }; let second:Pair=first; drop(second); return 0; }\n",
        "257\n263\n",
    ),
    (
        "replace",
        "fn main()->i32 { let old_left:Marker=Marker { prefix:1, number:269 }; let old_right:Marker=Marker { prefix:2, number:271 }; var target:Pair=Pair { left:old_left, code:3, right:old_right }; let new_left:Marker=Marker { prefix:4, number:277 }; let new_right:Marker=Marker { prefix:5, number:281 }; let replacement:Pair=Pair { left:new_left, code:6, right:new_right }; replace(target,replacement); drop(target); return 0; }\n",
        "269\n271\n277\n281\n",
    ),
    (
        "enum-match-transfer",
        "fn main()->i32 { let left:Marker=Marker { prefix:1, number:283 }; let right:Marker=Marker { prefix:2, number:293 }; let pair:Pair=Pair { left:left, code:3, right:right }; let packet:Packet=Spare(pair); match (packet) { Full(value) => { drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "283\n293\n",
    ),
)
MULTI_FIELD_SCALAR_AGGREGATE_SOURCE = (
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i64 { let pair:Pair=Pair { right:2, left:1 }; return pair.left*10+pair.right; }\n"
)
NESTED_MULTI_FIELD_AGGREGATE_SOURCE = (
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "struct Wrapper { pair:Pair; }\n"
    "fn main()->i64 { let pair:Pair=Pair { right:7, left:3 }; "
    "let wrapper:Wrapper=Wrapper { pair:pair }; drop(wrapper); return 37; }\n"
)
INVALID_MULTI_FIELD_AGGREGATE_SOURCES = (
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i32 { let pair:Pair=Pair { left:1, left:2 }; return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i32 { let pair:Pair=Pair { left:1 }; return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "fn main()->i32 { let pair:Pair=Pair { left:1, missing:2 }; return 0; }\n",
    "module main\nstruct First { value:i64; second:Second; }\n"
    "struct Second { value:i64; first:First; }\nfn main()->i32 { return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "destructor Pair { print(self.missing); }\nfn main()->i32 { return 0; }\n",
    "module main\nstruct Pair { left:i64; right:i64; }\n"
    "destructor Pair { print(self.left); }\ndestructor Pair { print(self.right); }\n"
    "fn main()->i32 { return 0; }\n",
)

PATH_SENSITIVE_OWNED_SOURCES = (
    (
        "scoped-if-explicit-drop",
        "fn main()->i32 { if 1<2 { let marker:Marker=Marker { number:137 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); } else {} return 0; }\n",
        "137\n",
    ),
    (
        "scoped-while-explicit-drop",
        "fn main()->i32 { var flag:i64=0; while flag<1 { let marker:Marker=Marker { number:139 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); flag=flag+1; } return 0; }\n",
        "139\n",
    ),
    (
        "outer-drop-converges",
        "fn main()->i32 { let marker:Marker=Marker { number:141 }; let owned:Wrapper=Wrapper { marker:marker }; if 1<2 { drop(owned); } else { drop(owned); } return 0; }\n",
        "141\n",
    ),
    (
        "drop-or-early-return",
        "fn main()->i32 { let marker:Marker=Marker { number:149 }; let owned:Wrapper=Wrapper { marker:marker }; if 1<2 { drop(owned); } else { return 0; } return 0; }\n",
        "149\n",
    ),
    (
        "scoped-replacement-transfer",
        "fn main()->i32 { let first:Marker=Marker { number:179 }; var target:Wrapper=Wrapper { marker:first }; if 1<2 { let second:Marker=Marker { number:181 }; let replacement:Wrapper=Wrapper { marker:second }; replace(target,replacement); } else {} drop(target); return 0; }\n",
        "179\n181\n",
    ),
    (
        "scoped-else-explicit-drop",
        "fn main()->i32 { if 2<1 {} else { let marker:Marker=Marker { number:193 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); } return 0; }\n",
        "193\n",
    ),
    (
        "scoped-drop-before-early-return",
        "fn main()->i32 { if 1<2 { let marker:Marker=Marker { number:199 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); return 0; } else {} return 1; }\n",
        "199\n",
    ),
    (
        "scoped-match-arm-cleanup",
        "fn main()->i32 { let marker:Marker=Marker { number:211 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Wrapped(outer); match (parcel) { Wrapped(value) => { let inner_marker:Marker=Marker { number:223 }; let arm_owned:Wrapper=Wrapper { marker:inner_marker }; drop(arm_owned); drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "223\n211\n",
    ),
)

PATH_SENSITIVE_CAPABILITY_OWNED_SOURCES = (
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "capability allocate;\n"
        + "fn main()->i32 { if 1<2 { with capability allocate { let marker:Marker=Marker { number:191 }; let scoped:Wrapper=Wrapper { marker:marker }; drop(scoped); } } else {} return 0; }\n",
        "191\n",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "capability allocate;\n"
        + "fn main()->i32 { with capability allocate { let marker:Marker=Marker { number:197 }; let function_owned:Wrapper=Wrapper { marker:marker }; } return 0; }\n",
        "197\n",
    ),
)

PATH_SENSITIVE_OWNED_REJECTIONS = (
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { if 1<2 { let marker:Marker=Marker { number:151 }; let leaked:Wrapper=Wrapper { marker:marker }; } else {} return 0; }\n",
        "M5212: scoped owned binding leaked",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:157 }; let owned:Wrapper=Wrapper { marker:marker }; if 1<2 { drop(owned); } else {} drop(owned); return 0; }\n",
        "M5101: binding owned already consumed",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:163 }; let owned:Wrapper=Wrapper { marker:marker }; drop(owned); drop(owned); return 0; }\n",
        "M5101: binding owned already consumed",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:167 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Wrapped(outer); match (parcel) { Wrapped(value) => { print(1); } Spare(value) => { drop(value); } } return 0; }\n",
        "M5211: owned match payload value",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { var flag:i64=0; while flag<1 { let marker:Marker=Marker { number:173 }; let leaked:Wrapper=Wrapper { marker:marker }; flag=flag+1; } return 0; }\n",
        "M5212: scoped owned binding leaked",
    ),
    (
        RECURSIVE_OWNED_AGGREGATE_PREFIX
        + "fn main()->i32 { let marker:Marker=Marker { number:227 }; let wrapper:Wrapper=Wrapper { marker:marker }; let outer:Outer=Outer { wrapper:wrapper }; let parcel:Parcel=Wrapped(outer); match (parcel) { Wrapped(value) => { let inner_marker:Marker=Marker { number:229 }; let leaked:Wrapper=Wrapper { marker:inner_marker }; drop(value); } Spare(value) => { drop(value); } } return 0; }\n",
        "M5212: scoped owned binding leaked",
    ),
)
SINGLE_I64_STRUCT_SOURCE = (
    "module main\n"
    "struct Box { value:i64; }\n"
    "fn main()->i64 { let box:Box=Box { value:7 }; return box.value; }\n"
)
INVALID_SINGLE_I64_STRUCT_FIELD_SOURCE = (
    "module main\n"
    "struct Box { value:i64; }\n"
    "fn main()->i64 { let box:Box=Box { wrong:7 }; return box.value; }\n"
)
INVALID_SINGLE_I64_STRUCT_REPLACE_SOURCE = (
    "module main\nstruct Box { value:i64; }\n"
    "fn main()->i64 { var target:Box=Box { value:1 }; let replacement:Box=Box { value:7 }; replace(target,replacement); return target.value; }\n"
)
SINGLE_I64_STRUCT_LIFECYCLE_SOURCES = (
    (
        "explicit-drop",
        "module main\nstruct Box { value:i64; }\n"
        "fn main()->i64 { let box:Box=Box { value:7 }; drop(box); return 7; }\n",
    ),
    (
        "move",
        "module main\nstruct Box { value:i64; }\n"
        "fn main()->i64 { let first:Box=Box { value:7 }; let second:Box=first; return second.value; }\n",
    ),
)
DESTRUCTOR_I64_STRUCT_LIFECYCLE_SOURCES = (
    (
        "implicit-cleanup",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let marker:Marker=Marker { number:7 }; return 0; }\n",
        "7\n",
    ),
    (
        "explicit-drop",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let marker:Marker=Marker { number:11 }; drop(marker); return 0; }\n",
        "11\n",
    ),
    (
        "move-no-double-drop",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let first:Marker=Marker { number:13 }; let second:Marker=first; drop(second); return 0; }\n",
        "13\n",
    ),
    (
        "early-return-cleanup",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { let marker:Marker=Marker { number:17 }; if 1<2 { return 0; } else { return 1; } }\n",
        "17\n",
    ),
    (
        "replace",
        "module main\nstruct Marker { number:i64; }\n"
        "destructor Marker { print(self.number); }\n"
        "fn main()->i32 { var target:Marker=Marker { number:1 }; let replacement:Marker=Marker { number:19 }; replace(target,replacement); drop(target); return 0; }\n",
        "1\n19\n",
    ),
)
UNSUPPORTED_DESTRUCTOR_I64_STRUCT_SOURCE = (
    "module main\nstruct Marker { number:i64; }\n"
    "destructor Marker { print(23); }\n"
    "fn main()->i32 { let marker:Marker=Marker { number:23 }; return 0; }\n"
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
def test_concrete_native_driver_executes_copy_payload_enum_lifecycle(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=PAYLOAD_ENUM_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=PAYLOAD_ENUM_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=PAYLOAD_ENUM_SOURCE,
        module_name="main",
        snapshot=bundle.functions[0],
        capability_names={},
    )
    instructions = [instruction for block in module.functions[0].blocks for instruction in block.instructions]
    assert [instruction.kind for instruction in instructions].count("construct") == 1
    assert [instruction.symbol for instruction in instructions if instruction.kind == "load_field"] == ["tag", "payload", "payload"]
    root = _project(tmp_path, PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")

    _, _, reference_executable = build(project, root / "build" / "reference-copy-payload-enum")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement-copy-payload-enum")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (7, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_owned_payload_enum_lifecycle(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path, OWNED_PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")

    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", OWNED_DESTRUCTOR_PAYLOAD_ENUM_SOURCES)
def test_concrete_native_driver_executes_owned_destructor_payload_enum_lifecycle(
    tmp_path: Path, case_name: str, body: str, expected_stdout: str
) -> None:
    source = OWNED_DESTRUCTOR_PAYLOAD_ENUM_PREFIX + body
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert any(local.type.name.startswith("enum_owned_payload_") for local in module.functions[0].locals)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_mixed_owned_payload_enum_shape(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run(
        [str(driver.executable)], input=UNSUPPORTED_MIXED_OWNED_PAYLOAD_ENUM_SOURCE,
        text=True, capture_output=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=UNSUPPORTED_MIXED_OWNED_PAYLOAD_ENUM_SOURCE,
        text=True, capture_output=True,
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    root = _project(tmp_path, UNSUPPORTED_MIXED_OWNED_PAYLOAD_ENUM_SOURCE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", RECURSIVE_OWNED_AGGREGATE_SOURCES)
def test_concrete_native_driver_executes_recursive_owned_aggregate_lifecycle(
    tmp_path: Path, case_name: str, body: str, expected_stdout: str
) -> None:
    source = RECURSIVE_OWNED_AGGREGATE_PREFIX + body
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    assert bundle.functions[0].type_descriptors
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert any(local.type.name.startswith("struct_owned_field_") for local in module.functions[0].locals)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_recursive_owned_aggregate_cycle(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=RECURSIVE_OWNED_AGGREGATE_CYCLE, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=RECURSIVE_OWNED_AGGREGATE_CYCLE, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    root = _project(tmp_path, RECURSIVE_OWNED_AGGREGATE_CYCLE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", MULTI_FIELD_OWNED_AGGREGATE_SOURCES)
def test_concrete_native_driver_executes_multi_field_owned_aggregate_lifecycle(
    tmp_path: Path, case_name: str, body: str, expected_stdout: str
) -> None:
    source = MULTI_FIELD_OWNED_AGGREGATE_PREFIX + body
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    aggregate_types = [
        local.type for local in module.functions[0].locals
        if local.type.name.startswith("struct_aggregate_")
    ]
    assert aggregate_types
    assert any(len(type_.arguments) == 3 for type_ in aggregate_types)

    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_named_multi_field_scalar_aggregate(tmp_path: Path) -> None:
    source = MULTI_FIELD_SCALAR_AGGREGATE_SOURCE
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout) == (12, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_one_field_wrapper_around_multi_field_aggregate(tmp_path: Path) -> None:
    source = NESTED_MULTI_FIELD_AGGREGATE_SOURCE
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout

    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout) == (37, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source", INVALID_MULTI_FIELD_AGGREGATE_SOURCES)
def test_concrete_native_driver_fails_closed_for_invalid_multi_field_aggregate(
    tmp_path: Path, source: str
) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    root = _project(tmp_path, source)
    try:
        project = load_project(root / "Merit.toml")
    except ProjectError:
        project = None
    if project is not None:
        with pytest.raises((CompileError, ReplacementProjectError)):
            prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,body,expected_stdout", PATH_SENSITIVE_OWNED_SOURCES)
def test_concrete_native_driver_executes_path_sensitive_owned_aggregate_control_flow(
    tmp_path: Path, case_name: str, body: str, expected_stdout: str
) -> None:
    source = RECURSIVE_OWNED_AGGREGATE_PREFIX + body
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")

    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    first = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    assert first.stdout == second.stdout
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)

    assert (replacement.returncode, replacement.stdout) == (
        reference.returncode,
        reference.stdout,
    )
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source,expected_stdout", PATH_SENSITIVE_CAPABILITY_OWNED_SOURCES)
def test_concrete_native_driver_tracks_enclosing_owned_scope_through_capability_region(
    tmp_path: Path, source: str, expected_stdout: str
) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")

    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    first = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True, check=True
    )
    assert first.stdout == second.stdout
    prepare_replacement_artifacts(project, driver)
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)

    assert (replacement.returncode, replacement.stdout) == (
        reference.returncode,
        reference.stdout,
    )
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source,reference_error", PATH_SENSITIVE_OWNED_REJECTIONS)
def test_concrete_native_driver_fails_closed_for_invalid_path_sensitive_ownership(
    tmp_path: Path, source: str, reference_error: str
) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True
    )
    second = subprocess.run(
        [str(driver.executable)], input=source, text=True, capture_output=True
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )
    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    with pytest.raises(CompileError, match=reference_error):
        build(project, root / "build" / "reference-invalid-ownership")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_non_copy_single_i64_struct_lifecycle(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=SINGLE_I64_STRUCT_SOURCE, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=SINGLE_I64_STRUCT_SOURCE, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=SINGLE_I64_STRUCT_SOURCE,
        module_name="main",
        snapshot=bundle.functions[0],
        capability_names={},
    )
    instructions = [instruction for block in module.functions[0].blocks for instruction in block.instructions]
    assert [instruction.kind for instruction in instructions].count("construct") == 1
    assert [instruction.symbol for instruction in instructions if instruction.kind == "load_field"] == ["field_0"]
    drops = [instruction for instruction in instructions if instruction.kind == "drop"]
    assert len(drops) == 1
    assert drops[0].ownership == "owned"

    root = _project(tmp_path, SINGLE_I64_STRUCT_SOURCE)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference-single-i64-struct")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)
    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement-single-i64-struct")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (7, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("source", [
    INVALID_SINGLE_I64_STRUCT_FIELD_SOURCE,
    INVALID_SINGLE_I64_STRUCT_REPLACE_SOURCE,
])
def test_concrete_native_driver_fails_closed_for_unrepresented_struct_shapes(tmp_path: Path, source: str) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True)
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)

    root = _project(tmp_path, source)
    project = load_project(root / "Merit.toml")
    if source == INVALID_SINGLE_I64_STRUCT_REPLACE_SOURCE:
        with pytest.raises(CompileError, match="replace requires owned storage"):
            build(project, root / "build" / "reference-invalid-replace")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_executes_single_i64_struct_drop_and_move(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    for case_name, source in SINGLE_I64_STRUCT_LIFECYCLE_SOURCES:
        root = _project(tmp_path / case_name, source)
        project = load_project(root / "Merit.toml")
        _, _, reference_executable = build(project, root / "build" / "reference")
        reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)

        first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
        second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
        assert first.stdout == second.stdout
        prepared = prepare_replacement_artifacts(project, driver)
        assert len(prepared.snapshot_paths) == 1
        artifact = build_replacement_project(project, root / "build" / "replacement")
        replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
        assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
        assert (replacement.returncode, replacement.stdout) == (7, "")


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
@pytest.mark.parametrize("case_name,source,expected_stdout", DESTRUCTOR_I64_STRUCT_LIFECYCLE_SOURCES)
def test_concrete_native_driver_executes_observable_i64_struct_destructor_lifecycle(
    tmp_path: Path, case_name: str, source: str, expected_stdout: str
) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    root = _project(tmp_path / case_name, source)
    project = load_project(root / "Merit.toml")
    _, _, reference_executable = build(project, root / "build" / "reference")
    reference = subprocess.run([str(reference_executable)], text=True, capture_output=True)

    first = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    second = subprocess.run([str(driver.executable)], input=source, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    bundle = decode_resolved_source_function_bundle(int(line) for line in first.stdout.splitlines())
    module = materialize_resolved_source_function_snapshot(
        source=source, module_name="main", snapshot=bundle.functions[0], capability_names={}
    )
    assert any(local.type.name.startswith("struct_i64_destructor_") for local in module.functions[0].locals)

    prepared = prepare_replacement_artifacts(project, driver)
    assert len(prepared.snapshot_paths) == 1
    artifact = build_replacement_project(project, root / "build" / "replacement")
    replacement = subprocess.run([str(artifact.executable)], text=True, capture_output=True)
    assert (replacement.returncode, replacement.stdout) == (reference.returncode, reference.stdout)
    assert (replacement.returncode, replacement.stdout) == (0, expected_stdout)


@pytest.mark.skipif(shutil.which("cc") is None and shutil.which("gcc") is None and shutil.which("clang") is None, reason="C compiler unavailable")
def test_concrete_native_driver_fails_closed_for_unrepresented_i64_struct_destructor(tmp_path: Path) -> None:
    driver = build_native_replacement_driver(tmp_path / "merit-native-replacement-driver")
    first = subprocess.run(
        [str(driver.executable)], input=UNSUPPORTED_DESTRUCTOR_I64_STRUCT_SOURCE,
        text=True, capture_output=True,
    )
    second = subprocess.run(
        [str(driver.executable)], input=UNSUPPORTED_DESTRUCTOR_I64_STRUCT_SOURCE,
        text=True, capture_output=True,
    )
    assert first.returncode != 0
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    root = _project(tmp_path, UNSUPPORTED_DESTRUCTOR_I64_STRUCT_SOURCE)
    project = load_project(root / "Merit.toml")
    with pytest.raises(ReplacementProjectError, match="replacement driver failed"):
        prepare_replacement_artifacts(project, driver)
    assert not (root / ".merit" / "replacement-build-v1.json").exists()
