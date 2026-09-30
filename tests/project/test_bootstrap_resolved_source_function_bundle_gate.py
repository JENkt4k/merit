from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import json

from merit.bootstrap.resolved_source_function_bundle import decode_resolved_source_function_bundle
from merit.bootstrap.resolved_source_function_snapshot import SNAPSHOT_SECTION_COUNT
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirTerminator,
    MirType,
    SourceSpan,
    canonical_mir_json,
)
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
  let effective_source:Buffer=buffer_new(allocator,0);
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
    effective_source,body,contracts,contract_locals,sources,bindings,ownership,cfg,placements,capabilities,type_descriptors,numeric_type_descriptors,
    destructor_descriptors,destructor_body,destructor_cfg,destructor_placements
  );
  if(first_status!=0){ return checked_add(10,first_status); }
  let second_status:i32=print_resolved_source_function_bundle_item(
    effective_source,body,contracts,contract_locals,sources,bindings,ownership,cfg,placements,capabilities,type_descriptors,numeric_type_descriptors,
    destructor_descriptors,destructor_body,destructor_cfg,destructor_placements
  );
  if(second_status!=0){ return checked_add(20,second_status); }

  drop(destructor_placements); drop(destructor_cfg); drop(destructor_body); drop(destructor_descriptors);
  drop(numeric_type_descriptors); drop(type_descriptors); drop(capabilities); drop(placements); drop(cfg); drop(ownership); drop(bindings);
  drop(sources); drop(contract_locals); drop(contracts); drop(body); drop(effective_source);
 }
 return 0;
}
'''

ARTIFACT_PROBE = PROBE.replace(
    "import bootstrap_mir_resolved_source_function_bundle;",
    "import bootstrap_mir_resolved_source_function_bundle;\nimport bootstrap_statement_semantics;",
).replace(
    "  let header_status:i32=print_resolved_source_function_bundle_header(2);",
    "  let header_status:i32=print_resolved_source_function_project_artifact_bundle_header(1);",
).replace(
    "  let second_status:i32=print_resolved_source_function_bundle_item(\n"
    "    effective_source,body,contracts,contract_locals,sources,bindings,ownership,cfg,placements,capabilities,type_descriptors,numeric_type_descriptors,\n"
    "    destructor_descriptors,destructor_body,destructor_cfg,destructor_placements\n"
    "  );\n"
    "  if(second_status!=0){ return checked_add(20,second_status); }",
    "  let metadata_source:Buffer=buffer_from_string(allocator,\"demo\");\n"
    "  var metadata_capabilities:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,0);\n"
    "  let metadata_status:i32=print_resolved_source_function_bundle_metadata(metadata_source,0,4,metadata_capabilities);\n"
    "  if(metadata_status!=0){ return checked_add(20,metadata_status); }\n"
    "  let canonical_mir:Buffer=buffer_from_string(allocator,\"mir\\n\");\n"
    "  let c_source:Buffer=buffer_from_string(allocator,\"c\\n\");\n"
    "  let c_header:Buffer=buffer_from_string(allocator,\"h\\n\");\n"
    "  let artifact_status:i32=print_resolved_source_function_project_artifacts(canonical_mir,c_source,c_header);\n"
    "  if(artifact_status!=0){ return checked_add(30,artifact_status); }\n"
    "  drop(c_header); drop(c_source); drop(canonical_mir);\n"
    "  drop(metadata_capabilities); drop(metadata_source);",
).replace("print_resolved_source_function_bundle_header(2)", "print_resolved_source_function_project_artifact_bundle_header(1)")

CANONICAL_MIR_PROBE = r'''module canonical_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"module demo\nfn compute()->i64 { return 1; }\n");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,5);
  vec_push<MirFunctionRecord>(records,function_mir_header(12,31,15,7,1));
  vec_push<MirFunctionRecord>(records,function_mir_temporary(0,1,0));
  vec_push<MirFunctionRecord>(records,function_mir_const(39,1,0,0,1,0));
  vec_push<MirFunctionRecord>(records,function_mir_print(39,1,1,0,1));
  vec_push<MirFunctionRecord>(records,function_mir_return(32,9,0,1));
  var output:Buffer=buffer_new(allocator,256);
  let status:i32=materialize_straight_line_canonical_mir(source,"demo",records,output);
  print(status); print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(records);drop(source);
  return status;
 }
}
'''

CFG_MIR_PROBE = r'''module cfg_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"module demo\nfn compute()->i64 { return; }\n");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,2);
  vec_push<MirFunctionRecord>(records,function_mir_header(12,29,15,7,1));
  vec_push<MirFunctionRecord>(records,function_mir_return(32,7,-1,0));
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,4);
  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));
  vec_push<MirCfgRecord>(cfg,cfg_jump(0,1));
  vec_push<MirCfgRecord>(cfg,cfg_block(1,1));
  vec_push<MirCfgRecord>(cfg,cfg_return_unit(1));
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);
  var output:Buffer=buffer_new(allocator,256);
  let status:i32=materialize_bounded_cfg_canonical_mir(source,"demo",records,cfg,placements,output);
  print(status);print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(placements);drop(cfg);drop(records);drop(source);
  return status;
 }
}
'''

INVALID_CFG_MIR_PROBE = CFG_MIR_PROBE.replace(
    "cfg_jump(0,1)", "cfg_jump(0,9)"
).replace("return status;", "return 0;")

PLACED_CFG_MIR_PROBE = CFG_MIR_PROBE.replace(
    "vec_new<MirFunctionRecord>(allocator,2)", "vec_new<MirFunctionRecord>(allocator,4)"
).replace(
    "fn compute()->i64 { return; }", "fn compute()->i64 { return 1; }"
).replace(
    "function_mir_header(12,29,15,7,1)", "function_mir_header(12,31,15,7,1)"
).replace(
    "vec_push<MirFunctionRecord>(records,function_mir_return(32,7,-1,0));",
    "vec_push<MirFunctionRecord>(records,function_mir_temporary(0,1,0));\n"
    "  vec_push<MirFunctionRecord>(records,function_mir_const(39,1,0,0,1,0));\n"
    "  vec_push<MirFunctionRecord>(records,function_mir_return(32,9,0,0));",
).replace(
    "cfg_return_unit(1)", "cfg_return(1,0)"
).replace(
    "vec_new<MirPlacementRecord>(allocator,0);",
    "vec_new<MirPlacementRecord>(allocator,1);\n  vec_push<MirPlacementRecord>(placements,mir_place(0,0,0));",
)

INVALID_PLACED_CFG_MIR_PROBE = PLACED_CFG_MIR_PROBE.replace(
    "mir_place(0,0,0)", "mir_place(9,0,0)"
).replace("return status;", "return 0;")

BRANCH_CFG_MIR_PROBE = PLACED_CFG_MIR_PROBE.replace(
    "function_mir_temporary(0,1,0)", "function_mir_temporary(0,2,0)"
).replace(
    "function_mir_const(39,1,0,0,1,0)", "function_mir_const(39,1,0,0,2,0)"
).replace(
    "vec_new<MirCfgRecord>(allocator,4)", "vec_new<MirCfgRecord>(allocator,6)"
).replace(
    "vec_push<MirCfgRecord>(cfg,cfg_jump(0,1));",
    "vec_push<MirCfgRecord>(cfg,cfg_branch(0,0,1,2));",
).replace(
    "vec_push<MirCfgRecord>(cfg,cfg_return(1,0));",
    "vec_push<MirCfgRecord>(cfg,cfg_return_unit(1));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(2,2));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_return_unit(2));",
)

SWITCH_CFG_MIR_PROBE = BRANCH_CFG_MIR_PROBE.replace(
    "vec_push<MirCfgRecord>(cfg,cfg_branch(0,0,1,2));",
    "vec_push<MirCfgRecord>(cfg,cfg_switch_case(0,0,7,1,0));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_switch_default(0,0,2,1));",
).replace(
    "vec_new<MirCfgRecord>(allocator,6)", "vec_new<MirCfgRecord>(allocator,7)"
)

OWNERSHIP_MIR_PROBE = r'''module ownership_mir_probe
import bootstrap_mir_ownership_flow;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn print_buffer(borrow value:Buffer)->i32 {
 print(buffer_len(value));var index:i64=0;
 while(index<buffer_len(value)){print(buffer_get(value,index));index=checked_add(index,1);}
 return 0;
}

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let move_record:MirOwnershipRecord=ownership_record(
   ownership_record_kind_move(),0,1,2,0,0,ownership_state_live(),ownership_state_moved()
  );
  let drop_record:MirOwnershipRecord=ownership_record(
   ownership_record_kind_implicit_drop(),1,2,ownership_record_no_other_binding_id(),1,1,
   ownership_state_live(),ownership_state_dropped()
  );
  let activation:MirOwnershipRecord=ownership_record(
   ownership_record_kind_activate(),ownership_record_no_instruction_id(),1,
   ownership_record_no_other_binding_id(),0,0,ownership_state_uninitialized(),ownership_state_live()
  );
  var move_output:Buffer=buffer_new(allocator,128);
  var drop_output:Buffer=buffer_new(allocator,128);
  print(materialize_canonical_ownership_instruction(move_record,3,1,move_output));
  print_buffer(move_output);
  print(materialize_canonical_ownership_instruction(drop_record,4,-1,drop_output));
  print_buffer(drop_output);
  print(materialize_canonical_ownership_instruction(activation,5,-1,drop_output));
  drop(drop_output);drop(move_output);
  return 0;
 }
}
'''

BUILTIN_TYPE_PROBE = r'''module builtin_type_probe
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  var code:i32=1;
  while(code<=14){
   var output:Buffer=buffer_new(allocator,32);
   print(canonical_mir_append_type(output,code));print(buffer_len(output));
   var index:i64=0;
   while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
   drop(output);code=code+1;
  }
  var invalid:Buffer=buffer_new(allocator,8);
  print(canonical_mir_append_type(invalid,99));drop(invalid);
  return 0;
 }
}
'''

NUMERIC_JSON_PROBE = r'''module numeric_json_probe
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"-12.5e+2");
  var output:Buffer=buffer_new(allocator,16);
  print(canonical_mir_append_json_source(output,source,0,8));print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(source);return 0;
 }
}
'''

STRING_JSON_PROBE = NUMERIC_JSON_PROBE.replace(
    'buffer_from_string(allocator,"-12.5e+2")',
    'buffer_from_string(allocator,"\\\"hello, world!\\\"")',
).replace("output,source,0,8", "output,source,0,15")


def _project(tmp_path: Path, probe: str = PROBE) -> Path:
    root = tmp_path / "resolved_source_function_bundle"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "resolved_source_function_bundle_probe.mrt").write_text(probe)
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


def _add_tail_status_marker(root: Path) -> None:
    snapshot = root / "src" / "mir_resolved_source_function_snapshot.mrt"
    text = snapshot.read_text()
    text, count = re.subn(
        r"(pub fn print_resolved_source_function_snapshot_with_source_policy\([\s\S]*?"
        r"borrow destructor_placements: Vec<MirPlacementRecord>)(\n\) -> i32)",
        r"\1,\n    call_abi_marker: i32\2",
        text,
        count=1,
    )
    assert count == 1
    text, count = re.subn(
        r"(pub fn print_resolved_source_function_snapshot_with_source_policy\([\s\S]*?\n\{)",
        r"\1\n    if (call_abi_marker != 1392) { return call_abi_marker; }",
        text,
        count=1,
    )
    assert count == 1
    text, count = re.subn(
        r"(destructor_body, destructor_cfg, destructor_placements)(\n    \);\n\})",
        r"\1, 1392\2",
        text,
        count=1,
    )
    assert count == 1
    snapshot.write_text(text)

    bundle = root / "src" / "mir_resolved_source_function_bundle.mrt"
    text = bundle.read_text()
    text, count = re.subn(
        r"(pub fn print_resolved_source_function_bundle_item_with_source_policy\([\s\S]*?"
        r"borrow destructor_placements: Vec<MirPlacementRecord>)(\n\) -> i32)",
        r"\1,\n    call_abi_marker: i32\2",
        text,
        count=1,
    )
    assert count == 1
    text, count = re.subn(
        r"(destructor_body, destructor_cfg, destructor_placements)(\n    \);\n\})",
        r"\1, call_abi_marker\2",
        text,
        count=1,
    )
    assert count == 1
    text, count = re.subn(
        r"(destructor_body, destructor_cfg, destructor_placements)(\n    \);\n\})",
        r"\1, 1392\2",
        text,
        count=1,
    )
    assert count == 1
    bundle.write_text(text)

    driver = root / "src" / "native_replacement_driver.mrt"
    text = driver.read_text()
    text, count = re.subn(
        r"(destructor_descriptors, destructor_body, destructor_cfg, destructor_placements)(\n"
        r"\s*\);)",
        r"\1, 1392\2",
        text,
        count=1,
    )
    assert count == 1
    driver.write_text(text)


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


def test_large_nested_call_preserves_tail_scalar_and_return_status(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _add_tail_status_marker(root)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "large-call-status")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = tuple(int(line) for line in native.splitlines())
    bundle = decode_resolved_source_function_bundle(values)
    assert len(bundle.functions) == 2


def test_native_v4_bundle_carries_complete_project_artifacts(tmp_path: Path) -> None:
    root = _project(tmp_path, ARTIFACT_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "native-artifact-bundle")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    bundle = decode_resolved_source_function_bundle(int(line) for line in native.splitlines())
    assert bundle.module_name == "demo"
    assert len(bundle.functions) == 1
    assert bundle.canonical_mir_bytes == b"mir\n"
    assert bundle.c_source_bytes == b"c\n"
    assert bundle.c_header_bytes == b"h\n"


def test_merit_materializes_straight_line_canonical_mir_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    assert values[1] == len(values) - 2
    actual = bytes(values[2:]).decode("utf-8")
    source = "module demo\nfn compute()->i64 { return 1; }\n"
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (MirLocal(0, "_t0", MirType("i64")),),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value="1", span=SourceSpan(39, 1), ownership="value"),
            MirInstruction(1, "print", operands=(0,), span=SourceSpan(39, 1)),
        ), MirTerminator("return", operands=(0,), span=SourceSpan(32, 9))),), 0,
    ),)))
    assert actual == expected


def test_merit_materializes_explicit_empty_cfg_topology(tmp_path: Path) -> None:
    root = _project(tmp_path, CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    assert values[1] == len(actual.encode("utf-8"))
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (), (
            MirBlock(0, (), MirTerminator("jump", targets=(1,))),
            MirBlock(1, (), MirTerminator("return")),
        ), 0,
    ),)))
    assert actual == expected


def test_merit_cfg_materializer_rejects_unknown_target(tmp_path: Path) -> None:
    root = _project(tmp_path, INVALID_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "invalid-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    assert interpreted.splitlines()[0] == "12"


def test_merit_materializes_explicit_instruction_placement(tmp_path: Path) -> None:
    root = _project(tmp_path, PLACED_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "placed-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (MirLocal(0, "_t0", MirType("i64")),), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(39, 1), ownership="value"),
            ), MirTerminator("jump", targets=(1,))),
            MirBlock(1, (), MirTerminator("return", operands=(0,))),
        ), 0,
    ),)))
    assert actual == expected


def test_merit_cfg_materializer_rejects_unplaced_instruction(tmp_path: Path) -> None:
    root = _project(tmp_path, INVALID_PLACED_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "invalid-placement")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    assert interpreted.splitlines()[0] == "28"


def test_merit_materializes_explicit_branch_topology(tmp_path: Path) -> None:
    root = _project(tmp_path, BRANCH_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "branch-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (MirLocal(0, "_t0", MirType("bool")),), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(39, 1), ownership="value"),
            ), MirTerminator("branch", operands=(0,), targets=(1, 2))),
            MirBlock(1, (), MirTerminator("return")),
            MirBlock(2, (), MirTerminator("return")),
        ), 0,
    ),)))
    assert actual == expected


def test_merit_materializes_explicit_switch_topology(tmp_path: Path) -> None:
    root = _project(tmp_path, SWITCH_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "switch-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (MirLocal(0, "_t0", MirType("bool")),), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(39, 1), ownership="value"),
            ), MirTerminator("switch", operands=(0,), targets=(1, 2), cases=(7,))),
            MirBlock(1, (), MirTerminator("return")),
            MirBlock(2, (), MirTerminator("return")),
        ), 0,
    ),)))
    assert actual == expected


def test_merit_materializes_explicit_ownership_effects(tmp_path: Path) -> None:
    root = _project(tmp_path, OWNERSHIP_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "ownership-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    move_length = values[1]
    move_json = bytes(values[2:2 + move_length]).decode("utf-8")
    drop_status_index = 2 + move_length
    assert values[drop_status_index] == 0
    drop_length = values[drop_status_index + 1]
    drop_json = bytes(values[drop_status_index + 2:drop_status_index + 2 + drop_length]).decode("utf-8")
    assert move_json == json.dumps(
        MirInstruction(3, "move", result=1, operands=(0,), ownership="owned").to_data(),
        sort_keys=True, separators=(",", ":"),
    )
    assert len(drop_json.encode("utf-8")) == drop_length
    assert drop_json == json.dumps(
        MirInstruction(4, "drop", operands=(1,), ownership="owned").to_data(),
        sort_keys=True, separators=(",", ":"),
    )
    assert values[drop_status_index + 2 + drop_length] == 3


def test_merit_materializes_complete_builtin_type_catalog(tmp_path: Path) -> None:
    root = _project(tmp_path, BUILTIN_TYPE_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "builtin-types")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    names = (
        "i64", "bool", "Allocator", "Buffer", "i8", "i16", "i32",
        "u8", "u16", "u32", "u64", "String", "ByteSlice", "unit",
    )
    cursor = 0
    for name in names:
        assert values[cursor] == 0
        length = values[cursor + 1]
        actual = bytes(values[cursor + 2:cursor + 2 + length]).decode("utf-8")
        assert actual == json.dumps(MirType(name).to_data(), sort_keys=True, separators=(",", ":"))
        cursor += 2 + length
    assert values[cursor] == 1


def test_merit_preserves_signed_decimal_numeric_spelling(tmp_path: Path) -> None:
    root = _project(tmp_path, NUMERIC_JSON_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "numeric-json")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    assert values[1] == len(actual.encode("utf-8"))
    assert actual == json.dumps("-12.5e+2", separators=(",", ":"))


def test_merit_escapes_source_backed_string_spelling(tmp_path: Path) -> None:
    root = _project(tmp_path, STRING_JSON_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "string-json")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    assert values[1] == len(actual.encode("utf-8"))
    assert actual == json.dumps('"hello, world!"', separators=(",", ":"))
