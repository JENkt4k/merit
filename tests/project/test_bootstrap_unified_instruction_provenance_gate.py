from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"

PROBE = r'''module unified_instruction_provenance_probe
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_function_ownership_assembly;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
capability allocate;

fn contract(kind:i32, clause:i64, ck:i32, id:i64, result:i64, left:i64) -> MirFunctionContractRecord {
 return MirFunctionContractRecord { kind:kind, clause_ordinal:clause, contract_kind:ck, start:1, length:1, id:id, result:result, left:left, right:-1, symbol:0, type_code:2, numeric_policy:1 };
}

fn main()->i32 { with capability allocate {
 let a:Allocator=system_allocator();
 var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(a,2);
 vec_push<MirOwnershipBinding>(bindings,ownership_binding(0,0,1,0));
 vec_push<MirOwnershipBinding>(bindings,ownership_binding(1,1,1,0));
 var input:Vec<MirOwnershipEvent>=vec_new<MirOwnershipEvent>(a,8);
 vec_push<MirOwnershipEvent>(input,ownership_event_place(0));
 vec_push<MirOwnershipEvent>(input,ownership_event_activate(0));
 vec_push<MirOwnershipEvent>(input,ownership_event_move(0,1));
 vec_push<MirOwnershipEvent>(input,ownership_event_drop(1));
 vec_push<MirOwnershipEvent>(input,ownership_event_return(-1));
 var owned_events:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(a,16);
 var owned_records:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(a,8);
 print(lower_ownership_flow(input,bindings,a,owned_events,owned_records));
 print(validate_ownership_records(owned_records,bindings));

 var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(a,8);
 vec_push<MirFunctionContractRecord>(contracts,contract(1,0,1,2,-1,-1));
 vec_push<MirFunctionContractRecord>(contracts,contract(2,0,1,0,2,-1));
 vec_push<MirFunctionContractRecord>(contracts,contract(4,0,1,1,-1,2));
 vec_push<MirFunctionContractRecord>(contracts,contract(1,1,2,3,-1,-1));
 vec_push<MirFunctionContractRecord>(contracts,contract(2,1,2,2,3,-1));
 vec_push<MirFunctionContractRecord>(contracts,contract(4,1,2,3,-1,3));
 print(validate_function_contract_mir(contracts));

 var events:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(a,24);
 var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(a,16);
 print(assemble_function_mir_events_with_ownership(contracts,owned_events,owned_records,bindings,2,2,1,a,events,sources));
 print(validate_function_assembly_sources(sources));
 print(vec_len<MirFunctionInstructionSource>(sources));
 var i:i64=0;
 while(i<vec_len<MirFunctionInstructionSource>(sources)){
  let s:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,i);
  print(assembly_source_global_id(s));print(assembly_source_kind(s));print(assembly_source_id(s));
  print(assembly_source_result(s));print(assembly_source_left(s));
  i=checked_add(i,1);
 }
 var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(a,8);
 var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(a,16);
 print(lower_structured_mir(events,a,cfg,placements));
 print(vec_len<MirPlacementRecord>(placements));
 print(vec_len<MirCfgRecord>(cfg));
 drop(placements);drop(cfg);drop(sources);drop(events);drop(contracts);drop(owned_records);drop(owned_events);drop(input);drop(bindings);
 } return 0; }
'''


def _project(tmp_path):
    root = tmp_path / "unified_instruction_provenance"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src/lexer.mrt"
    text, n = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert n == 1
    lexer.write_text(text)
    (root / "src/unified_instruction_provenance_probe.mrt").write_text(PROBE)
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text().replace('entry = "src/lexer.mrt"', 'entry = "src/unified_instruction_provenance_probe.mrt"'))
    return load_project(manifest), root


def _values(output: str):
    return [int(v) for v in output.splitlines()]


def test_body_ownership_and_contract_instructions_share_one_dense_namespace(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _values(interpret(project))
    assert interpreted[:5] == [0, 0, 0, 0, 0]
    assert interpreted[5] == 7
    rows = [tuple(interpreted[i:i + 5]) for i in range(6, 41, 5)]
    assert [row[0] for row in rows] == list(range(7))
    assert [row[1] for row in rows] == [1, 1, 2, 3, 3, 1, 1]
    assert [row[2] for row in rows] == [0, 1, 0, 1, 2, 2, 3]
    assert rows[3][3:] == (1, 0)
    assert rows[4][3:] == (-1, 1)
    assert interpreted[41:] == [0, 7, 2]
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _values(native) == interpreted
