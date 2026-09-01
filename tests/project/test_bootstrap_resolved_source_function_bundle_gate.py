from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.resolved_source_function_bundle import decode_resolved_source_function_bundle
from merit.bootstrap.resolved_source_function_snapshot import SNAPSHOT_SECTION_COUNT
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"

PROBE = r'''module resolved_source_function_bundle_probe
import bootstrap_mir_functions;
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_assembly_plan;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_snapshot;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,0);
  var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,0);
  var contract_locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,0);
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,0);
  var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,0);
  var ownership:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,0);
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,0);
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);
  var capabilities:Vec<i64>=vec_new<i64>(allocator,0);
  var type_descriptors:Vec<MirTypeDescriptor>=vec_new<MirTypeDescriptor>(allocator,0);
  var numeric_type_descriptors:Vec<MirNumericTypeDescriptor>=vec_new<MirNumericTypeDescriptor>(allocator,0);
  var destructor_descriptors:Vec<MirDestructorDescriptor>=vec_new<MirDestructorDescriptor>(allocator,0);
  var destructor_body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,0);
  var destructor_cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,0);
  var destructor_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);

  let header_status:i32=print_resolved_source_function_bundle_header(2);
  if(header_status!=0){ return header_status; }
  let first_status:i32=print_resolved_source_function_bundle_item(
    body,contracts,contract_locals,sources,bindings,ownership,cfg,placements,capabilities,type_descriptors,numeric_type_descriptors,
    destructor_descriptors,destructor_body,destructor_cfg,destructor_placements
  );
  if(first_status!=0){ return checked_add(10,first_status); }
  let second_status:i32=print_resolved_source_function_bundle_item(
    body,contracts,contract_locals,sources,bindings,ownership,cfg,placements,capabilities,type_descriptors,numeric_type_descriptors,
    destructor_descriptors,destructor_body,destructor_cfg,destructor_placements
  );
  if(second_status!=0){ return checked_add(20,second_status); }

  drop(destructor_placements); drop(destructor_cfg); drop(destructor_body); drop(destructor_descriptors);
  drop(numeric_type_descriptors); drop(type_descriptors); drop(capabilities); drop(placements); drop(cfg); drop(ownership); drop(bindings);
  drop(sources); drop(contract_locals); drop(contracts); drop(body);
 }
 return 0;
}
'''


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "resolved_source_function_bundle"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "resolved_source_function_bundle_probe.mrt").write_text(PROBE)
    manifest = root / "Merit.toml"
    text = manifest.read_text()
    text, count = re.subn(
        r'entry\s*=\s*"src/lexer\.mrt"',
        'entry = "src/resolved_source_function_bundle_probe.mrt"',
        text,
        count=1,
    )
    assert count == 1
    manifest.write_text(text)
    return root


def test_native_bundle_framing_matches_interpreter_and_python_decoder(tmp_path: Path) -> None:
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "resolved-source-function-bundle")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = tuple(int(line) for line in native.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 2
    assert len(bundle.encoded_snapshots) == 2
    assert all(len(snapshot) == 2 + SNAPSHOT_SECTION_COUNT for snapshot in bundle.encoded_snapshots)
