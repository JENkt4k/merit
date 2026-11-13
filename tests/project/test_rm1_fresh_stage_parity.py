"""Fresh public compiler stages independently agree on the bounded RM1 corpus."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from merit.bootstrap import self_hosting as sh
from merit.bootstrap.mir_contract import parse_mir
from merit.bootstrap.resolved_source_function_bundle import (
    BUNDLE_MAGIC,
    LOCAL_LOAN_PROJECT_ARTIFACT_BUNDLE_VERSION,
    decode_native_project_artifact_transport,
)
from merit.project.replacement_prepare import (
    _LOCAL_LOAN_DIAGNOSTIC_MAGIC,
    _LOCAL_LOAN_DIAGNOSTIC_VERSION,
)
from merit.project.project_request import (
    ProjectRequest,
    ProjectRequestUnit,
    encode_project_request,
)


ACCEPTED = {
    "01": ('let x:String="a"; let r: borrow String=borrow x; print(r);', ""),
    "02": ('let x:String="a"; let r: borrow String=borrow x; '
           'let s: borrow String=borrow x; print(r); print(s);', ""),
    "04": ('var x:i32=1; let r: borrow i32=borrow x; print(r); x=2;', ""),
    "07": ('let x:Box=Box {value:1}; let r: borrow Box=borrow x; '
           'print(r.value); let y:Box=x; print(y.value);',
           'struct Box { value:i32; }\n'),
    "09": ('let x:String="a"; let r: borrow String=borrow x; print(r); drop(x);', ""),
    "18": ('var x:i32=1; with capability io { let r: borrow i32=borrow x; '
           'print(r); } x=2;', 'capability io;\n'),
    "24": ('let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r);',
           'fn inspect(borrow value:i32)->i32 { return value; }\n'),
}
REJECTED = {
    "05": ('var x:i32=1; let r: borrow i32=borrow x; x=2; print(r);', "", 5402),
    "06": ('let x:Box=Box {value:1}; let r: borrow Box=borrow x; '
           'let y:Box=x; print(r.value);', 'struct Box { value:i32; }\n', 5402),
    "08": ('let x:String="a"; let r: borrow String=borrow x; drop(x); print(r);', "", 5402),
    "22": ('let x:i32=1; let r: borrow i32=borrow x; return r;', "", 5404),
    "23": ('let x:i32=1; let r: borrow i32=borrow x; '
           'let h:Holder=Holder {value:r};', 'struct Holder { value:i32; }\n', 5404),
    "28": ('let x:String="a"; let r: borrow String=borrow x; '
           'replace(x,"b"); print(r);', "", 5402),
}


def _request(body: str, declarations: str) -> bytes:
    source = f'module probe\n{declarations}fn main()->i32 {{ {body} return 0; }}\n'
    return encode_project_request(ProjectRequest(
        "probe", "src/main.mrt",
        (ProjectRequestUnit("src/main.mrt", source.encode("utf-8")),),
        header_exports=(),
    ))


def test_fresh_public_stages_agree_on_rm1_v5_and_rejections(tmp_path: Path) -> None:
    stages = sh.build_stages(tmp_path / "rm1-stages")
    assert sh.compare_stage_bytes(stages)
    for case, (body, declarations) in ACCEPTED.items():
        request = _request(body, declarations)
        observations = [sh.run_probe(stage.executable, request) for stage in stages]
        assert len(set(observations)) == 1, case
        status, stdout, stderr = observations[0]
        assert status == 0, (case, stderr)
        transport = decode_native_project_artifact_transport(
            int(line) for line in stdout.splitlines()
        )
        assert transport.version == LOCAL_LOAN_PROJECT_ARTIFACT_BUNDLE_VERSION, case
        assert parse_mir(json.loads(transport.canonical_mir_bytes)).schema == "bootstrap-mir-v2", case
        assert transport.c_source_bytes and transport.c_header_bytes, case
    for case, (body, declarations, code) in REJECTED.items():
        request = _request(body, declarations)
        observations = [sh.run_probe(stage.executable, request) for stage in stages]
        assert len(set(observations)) == 1, case
        status, stdout, stderr = observations[0]
        assert status != 0, case
        assert b"replacement driver status 907" in stderr, case
        rows = [int(line) for line in stdout.splitlines()]
        assert rows[:3] == [BUNDLE_MAGIC, LOCAL_LOAN_PROJECT_ARTIFACT_BUNDLE_VERSION, 0], case
        assert rows[3:6] == [_LOCAL_LOAN_DIAGNOSTIC_MAGIC,
                             _LOCAL_LOAN_DIAGNOSTIC_VERSION, code], case

    # The stage probes above compare the native producer directly. Also make
    # one complete feature build through the installed public project command
    # at each stage, including native C compilation and executable output.
    public_artifacts = []
    public_outputs = []
    for stage in stages:
        project = tmp_path / f"public-{stage.name}"
        source = project / "src" / "main.mrt"
        source.parent.mkdir(parents=True)
        source.write_text(
            'module probe\nfn main()->i32 { let x:i32=1; '
            'let r: borrow i32=borrow x; print(r); return 0; }\n',
            encoding="utf-8", newline="\n",
        )
        (project / "Merit.toml").write_text(
            '[package]\nname="probe"\nentry="src/main.mrt"\n'
            'sources=["src/**/*.mrt"]\n', encoding="utf-8", newline="\n",
        )
        output = tmp_path / f"program-{stage.name}"
        command = (str(sh.project_command()), "build", str(project),
                   "--compiler-path", str(stage.executable), "-o", str(output))
        built = subprocess.run(command, capture_output=True, timeout=3600)
        assert built.returncode == 0, (stage.name, built.stderr.decode(errors="replace"))
        executable = Path(built.stdout.decode().strip())
        assert executable.is_file(), stage.name
        ran = subprocess.run((str(executable),), capture_output=True, timeout=30)
        assert ran.returncode == 0, (stage.name, ran.stderr)
        public_outputs.append(ran.stdout.replace(b"\r\n", b"\n"))
        manifest = json.loads((project / ".merit" / "replacement-build-v1.json").read_text(
            encoding="utf-8"
        ))
        assert manifest["producer_protocol"].endswith("bundle-v5"), stage.name
        public_artifacts.append(tuple(
            (project / ".merit" / manifest["native_artifacts"][label]["path"]).read_bytes()
            for label in ("canonical_mir", "c_source", "c_header")
        ))
    assert public_outputs == [b"1\n"] * len(stages)
    assert len(set(public_artifacts)) == 1
