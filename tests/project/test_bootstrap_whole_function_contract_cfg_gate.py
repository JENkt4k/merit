from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"

PROBE = r'''module bootstrap_whole_function_contract_cfg_probe
import bootstrap_mir_function_clause_metadata;
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_assembly_plan;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_function_assembly;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;

capability allocate;

fn contract_record(kind:i32, clause:i64, ck:i32, id:i64, result:i64, left:i64, right:i64, symbol:i32, type_code:i32, policy:i32) -> MirFunctionContractRecord {
    return MirFunctionContractRecord { kind:kind, clause_ordinal:clause, contract_kind:ck, start:1, length:1, id:id, result:result, left:left, right:right, symbol:symbol, type_code:type_code, numeric_policy:policy };
}

fn main() -> i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  var metadata:Vec<MirFunctionClauseMetadata>=vec_new<MirFunctionClauseMetadata>(allocator,1);
  vec_push<MirFunctionClauseMetadata>(metadata,MirFunctionClauseMetadata { kind:2, clause_ordinal:0, operand_ordinal:0, start:1, length:5, semantic_id:9 });

  var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,16);
  vec_push<MirFunctionContractRecord>(contracts,contract_record(1,1,1,0,-1,-1,-1,0,2,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(1,1,1,1,-1,-1,-1,0,1,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(1,1,1,2,-1,-1,-1,0,1,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(2,1,1,0,1,-1,-1,0,1,1));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(2,1,1,1,2,-1,-1,0,1,1));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(3,1,1,2,0,1,2,10,2,1));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(4,1,1,3,-1,0,-1,0,2,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(1,2,2,3,-1,-1,-1,0,2,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(1,2,2,4,-1,-1,-1,0,1,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(1,2,2,5,-1,-1,-1,0,1,0));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(2,2,2,4,4,-1,-1,0,1,1));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(2,2,2,5,5,-1,-1,0,1,1));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(3,2,2,6,3,4,5,9,2,1));
  vec_push<MirFunctionContractRecord>(contracts,contract_record(4,2,2,7,-1,3,-1,0,2,0));

  var body:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,8);
  vec_push<MirLowerEvent>(body,mir_event_place(0));
  vec_push<MirLowerEvent>(body,mir_event_if(0));
  vec_push<MirLowerEvent>(body,mir_event_place(1));
  vec_push<MirLowerEvent>(body,mir_event_return(1));
  vec_push<MirLowerEvent>(body,mir_event_end_if());
  vec_push<MirLowerEvent>(body,mir_event_place(2));
  vec_push<MirLowerEvent>(body,mir_event_return(2));

  var locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,8);
  var caps:Vec<i64>=vec_new<i64>(allocator,2);
  print(plan_function_contract_namespace(metadata,contracts,0,3,locals,caps));
  let local0:MirFunctionContractLocal=vec_get<MirFunctionContractLocal>(locals,0);
  let local5:MirFunctionContractLocal=vec_get<MirFunctionContractLocal>(locals,5);
  print(vec_len<MirFunctionContractLocal>(locals)); print(assembly_local_id(local0)); print(assembly_local_id(local5));
  print(vec_len<i64>(caps)); print(vec_get<i64>(caps,0));

  var events:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,32);
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,32);
  print(assemble_function_mir_events(contracts,body,0,3,allocator,events,sources));
  print(validate_function_assembly_sources(sources)); print(vec_len<MirFunctionInstructionSource>(sources));
  let source0:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,0);
  let source4:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,4);
  let source6:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,6);
  let source11:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,11);
  let source2:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,2);
  let source3:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,3);
  print(assembly_source_kind(source0)); print(assembly_source_kind(source4));
  print(assembly_source_contract_kind(source6)); print(assembly_source_id(source6));
  print(assembly_source_contract_kind(source11)); print(assembly_source_id(source11));
  print(assembly_source_result(source2)); print(assembly_source_left(source3));

  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,16);
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,32);
  print(lower_structured_mir(events,allocator,cfg,placements));
  let placement0:MirPlacementRecord=vec_get<MirPlacementRecord>(placements,0);
  let placement5:MirPlacementRecord=vec_get<MirPlacementRecord>(placements,5);
  let placement10:MirPlacementRecord=vec_get<MirPlacementRecord>(placements,10);
  print(vec_len<MirCfgRecord>(cfg)); print(vec_len<MirPlacementRecord>(placements));
  print(placement_block_id(placement0)); print(placement_block_id(placement5)); print(placement_block_id(placement10));

  drop(placements);drop(cfg);drop(sources);drop(events);drop(caps);drop(locals);drop(body);drop(contracts);drop(metadata);
 }
 return 0;
}
'''


def _project(tmp_path: Path):
    root = tmp_path / "whole_function_contract_cfg"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1)
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "whole_function_contract_cfg_probe.mrt").write_text(PROBE, encoding="utf-8")
    manifest = root / "Merit.toml"
    text = manifest.read_text(encoding="utf-8").replace('entry = "src/lexer.mrt"', 'entry = "src/whole_function_contract_cfg_probe.mrt"')
    manifest.write_text(text, encoding="utf-8")
    return load_project(manifest), root


def _values(output: str) -> list[int]:
    return [int(value) for value in output.splitlines()]


def test_contracts_capabilities_and_two_returns_share_one_native_cfg(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _values(interpret(project))
    assert interpreted == [0, 6, 3, 8, 1, 9, 0, 0, 15, 1, 2, 2, 4, 2, 4, 3, 3, 0, 8, 15, 0, 1, 3]
    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _values(native) == interpreted
