from __future__ import annotations

from pathlib import Path
import re, shutil, subprocess
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"

PROBE = r'''module bootstrap_match_ownership_probe
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_ownership_flow;
capability allocate;

fn main() -> i32 {
  with capability allocate {
    let a: Allocator = system_allocator();
    var b: Vec<MirOwnershipBinding> = vec_new<MirOwnershipBinding>(a, 2);
    vec_push<MirOwnershipBinding>(b, ownership_binding(0,0,1,0));
    vec_push<MirOwnershipBinding>(b, ownership_binding(1,1,1,0));
    var e: Vec<MirOwnershipEvent> = vec_new<MirOwnershipEvent>(a, 20);
    vec_push<MirOwnershipEvent>(e, ownership_event_activate(0));
    vec_push<MirOwnershipEvent>(e, ownership_event_activate(1));
    vec_push<MirOwnershipEvent>(e, ownership_event_match(10,3));
    vec_push<MirOwnershipEvent>(e, ownership_event_case(0,0));
    vec_push<MirOwnershipEvent>(e, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(e, ownership_event_return(100));
    vec_push<MirOwnershipEvent>(e, ownership_event_case(1,1));
    vec_push<MirOwnershipEvent>(e, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(e, ownership_event_case(2,2));
    vec_push<MirOwnershipEvent>(e, ownership_event_drop(0));
    vec_push<MirOwnershipEvent>(e, ownership_event_end_match());
    vec_push<MirOwnershipEvent>(e, ownership_event_return(200));
    var l: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(a, 32);
    var r: Vec<MirOwnershipRecord> = vec_new<MirOwnershipRecord>(a, 24);
    print(lower_ownership_flow(e,b,a,l,r)); print(validate_ownership_records(r,b));
    print(vec_len<MirLowerEvent>(l));
    var i:i64=0; while(i<vec_len<MirLowerEvent>(l)){ let x:MirLowerEvent=vec_get<MirLowerEvent>(l,i); print(lower_event_kind(x)); print(lower_event_a(x)); print(lower_event_b(x)); i=checked_add(i,1); }
    var c:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(a,48); var p:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(a,16);
    print(lower_structured_mir(l,a,c,p));
    var conflict:Vec<MirOwnershipEvent>=vec_new<MirOwnershipEvent>(a,10);
    vec_push<MirOwnershipEvent>(conflict,ownership_event_activate(0)); vec_push<MirOwnershipEvent>(conflict,ownership_event_activate(1));
    vec_push<MirOwnershipEvent>(conflict,ownership_event_match(10,2)); vec_push<MirOwnershipEvent>(conflict,ownership_event_case(0,0));
    vec_push<MirOwnershipEvent>(conflict,ownership_event_drop(0)); vec_push<MirOwnershipEvent>(conflict,ownership_event_case(1,1)); vec_push<MirOwnershipEvent>(conflict,ownership_event_end_match());
    var cl:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(a,16); var cr:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(a,16); print(lower_ownership_flow(conflict,b,a,cl,cr));
    drop(cr);drop(cl);drop(conflict);drop(p);drop(c);drop(r);drop(l);drop(e);drop(b);
  }
  return 0;
}
'''


def _project(tmp_path: Path):
    root = tmp_path / "match_ownership"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src/lexer.mrt"
    text, n = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert n == 1
    lexer.write_text(text)
    (root / "src/match_ownership_probe.mrt").write_text(PROBE)
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text().replace('entry = "src/lexer.mrt"','entry = "src/match_ownership_probe.mrt"'))
    return load_project(manifest), root


def _parse(s: str):
    v=[int(x) for x in s.splitlines()]; status,valid,count=v[:3]; q=3
    events=[tuple(v[q+i:q+i+3]) for i in range(0,count*3,3)]; q+=count*3
    return status,valid,events,v[q],v[q+1]


def test_match_ownership_n_way_merge_and_structured_mir(tmp_path):
    project, root = _project(tmp_path)
    got = _parse(interpret(project))
    assert got[0:2] == (0,0)
    assert [x[0] for x in got[2]] == [30,31,1,1,2,31,1,31,1,32,3,33,1,2]
    assert got[2][0] == (30,10,4)
    assert [x[1] for x in got[2] if x[0] == 31] == [0,1,2]
    assert got[3] == 0
    assert got[4] == 80
    _,_,exe = build(project, root / "native")
    assert _parse(subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout) == got
