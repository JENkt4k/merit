from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import json
import pytest

from merit.bootstrap.resolved_source_function_bundle import decode_resolved_source_function_bundle
from merit.bootstrap.resolved_source_function_snapshot import SNAPSHOT_SECTION_COUNT
from merit.bootstrap.mir_contract import (
    MirBlock,
    MirFunction,
    MirInstruction,
    MirLocal,
    MirModule,
    MirParameter,
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

CANONICAL_PROJECT_ASSEMBLY_PROBE = r'''module canonical_project_assembly_probe
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let first:Buffer=buffer_from_string(allocator,"{\"functions\":[{\"name\":\"first\"}],\"name\":\"_\",\"schema\":\"bootstrap-mir-v1\"}");
  let second:Buffer=buffer_from_string(allocator,"{\"functions\":[{\"name\":\"second\"}],\"name\":\"_\",\"schema\":\"bootstrap-mir-v1\"}");
  var output:Buffer=buffer_new(allocator,256);
  let begin_status:i32=canonical_mir_begin_project(output);
  if(begin_status!=0){return begin_status;}
  let first_status:i32=canonical_mir_append_project_function(first,0,allocator,output);
  if(first_status!=0){return checked_add(10,first_status);}
  let second_status:i32=canonical_mir_append_project_function(second,1,allocator,output);
  if(second_status!=0){return checked_add(20,second_status);}
  let finish_status:i32=canonical_mir_finish_project("demo",2,output);
  if(finish_status!=0){return checked_add(30,finish_status);}
  print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(second);drop(first);
 }
 return 0;
}
'''

CANONICAL_C_BACKEND_PROBE = r'''module canonical_c_backend_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"compute23");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,8);
  vec_push<MirFunctionRecord>(records,function_mir_callable_header(0,9,0,7,function_mir_i64_type_code(),function_mir_mode_value(),-1,0,1));
  vec_push<MirFunctionRecord>(records,function_mir_temporary(0,function_mir_i64_type_code(),0));
  vec_push<MirFunctionRecord>(records,function_mir_temporary(1,function_mir_i64_type_code(),1));
  vec_push<MirFunctionRecord>(records,function_mir_temporary(2,function_mir_i64_type_code(),2));
  vec_push<MirFunctionRecord>(records,function_mir_const(7,1,0,0,function_mir_i64_type_code(),0));
  vec_push<MirFunctionRecord>(records,function_mir_const(8,1,1,1,function_mir_i64_type_code(),1));
  vec_push<MirFunctionRecord>(records,function_mir_binary(7,2,2,2,0,1,function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy(),2));
  vec_push<MirFunctionRecord>(records,function_mir_print(7,2,3,2,3));
  vec_push<MirFunctionRecord>(records,function_mir_return(7,2,2,4));
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,2);
  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));vec_push<MirCfgRecord>(cfg,cfg_return(0,2));
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,4);
  vec_push<MirPlacementRecord>(placements,mir_place(0,0,0));vec_push<MirPlacementRecord>(placements,mir_place(0,1,1));
  vec_push<MirPlacementRecord>(placements,mir_place(0,2,2));vec_push<MirPlacementRecord>(placements,mir_place(0,3,3));
  var features:Vec<i64>=vec_new<i64>(allocator,2);
  var prototypes:Buffer=buffer_new(allocator,64);var bodies:Buffer=buffer_new(allocator,256);
  var declarations:Buffer=buffer_new(allocator,64);var c_source:Buffer=buffer_new(allocator,512);
  var c_header:Buffer=buffer_new(allocator,256);
  let function_status:i32=canonical_c_append_scalar_function(source,records,cfg,placements,prototypes,bodies,declarations,features);
  if(function_status!=0){return function_status;}
  let source_status:i32=canonical_c_finish_scalar_module(prototypes,bodies,features,c_source);
  if(source_status!=0){return checked_add(100,source_status);}
  let header_status:i32=canonical_c_finish_public_header(declarations,c_header);
  if(header_status!=0){return checked_add(200,header_status);}
  print(buffer_len(c_source));var index:i64=0;
  while(index<buffer_len(c_source)){print(buffer_get(c_source,index));index=checked_add(index,1);}
  print(buffer_len(c_header));index=0;
  while(index<buffer_len(c_header)){print(buffer_get(c_header,index));index=checked_add(index,1);}
  drop(c_header);drop(c_source);drop(declarations);drop(bodies);drop(prototypes);
  drop(features);drop(placements);drop(cfg);drop(records);drop(source);
 }
 return 0;
}
'''

CANONICAL_C_MULTIFUNCTION_PROBE = r'''module canonical_c_multifunction_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"first1second");
  var first:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,4);
  vec_push<MirFunctionRecord>(first,function_mir_callable_header(0,6,0,5,function_mir_i64_type_code(),function_mir_mode_value(),-1,0,0));
  vec_push<MirFunctionRecord>(first,function_mir_temporary(0,function_mir_i64_type_code(),0));
  vec_push<MirFunctionRecord>(first,function_mir_const(5,1,0,0,function_mir_i64_type_code(),0));
  vec_push<MirFunctionRecord>(first,function_mir_return(5,1,0,0));
  var second:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,3);
  vec_push<MirFunctionRecord>(second,function_mir_callable_header(6,6,6,6,function_mir_i64_type_code(),function_mir_mode_value(),-1,1,1));
  vec_push<MirFunctionRecord>(second,function_mir_parameter(6,6,0,function_mir_i64_type_code(),0,0,function_mir_mode_value(),0));
  vec_push<MirFunctionRecord>(second,function_mir_return(6,6,0,0));
  var first_cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,2);
  vec_push<MirCfgRecord>(first_cfg,cfg_block(0,0));vec_push<MirCfgRecord>(first_cfg,cfg_return(0,0));
  var second_cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,2);
  vec_push<MirCfgRecord>(second_cfg,cfg_block(0,0));vec_push<MirCfgRecord>(second_cfg,cfg_return(0,0));
  var first_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,1);
  vec_push<MirPlacementRecord>(first_placements,mir_place(0,0,0));
  var second_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);
  var features:Vec<i64>=vec_new<i64>(allocator,0);
  var prototypes:Buffer=buffer_new(allocator,128);var bodies:Buffer=buffer_new(allocator,512);
  var declarations:Buffer=buffer_new(allocator,128);var c_source:Buffer=buffer_new(allocator,1024);
  var c_header:Buffer=buffer_new(allocator,256);
  let first_status:i32=canonical_c_append_scalar_function(source,first,first_cfg,first_placements,prototypes,bodies,declarations,features);
  if(first_status!=0){return first_status;}
  let second_status:i32=canonical_c_append_scalar_function(source,second,second_cfg,second_placements,prototypes,bodies,declarations,features);
  if(second_status!=0){return checked_add(100,second_status);}
  let source_status:i32=canonical_c_finish_scalar_module(prototypes,bodies,features,c_source);
  if(source_status!=0){return checked_add(200,source_status);}
  let header_status:i32=canonical_c_finish_public_header(declarations,c_header);
  if(header_status!=0){return checked_add(300,header_status);}
  print(buffer_len(c_source));var index:i64=0;
  while(index<buffer_len(c_source)){print(buffer_get(c_source,index));index=checked_add(index,1);}
  print(buffer_len(c_header));index=0;
  while(index<buffer_len(c_header)){print(buffer_get(c_header,index));index=checked_add(index,1);}
  drop(c_header);drop(c_source);drop(declarations);drop(bodies);drop(prototypes);
  drop(features);drop(second_placements);drop(first_placements);drop(second_cfg);drop(first_cfg);
  drop(second);drop(first);drop(source);
 }
 return 0;
}
'''

CANONICAL_C_I32_MULTIFUNCTION_PROBE = CANONICAL_C_MULTIFUNCTION_PROBE.replace(
    "function_mir_i64_type_code()", "function_mir_i32_type_code()",
)
CANONICAL_C_UNIT_CALL_PROBE = r'''module canonical_c_unit_call_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"pingrun");
  var first:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,2);
  vec_push<MirFunctionRecord>(first,function_mir_callable_header(0,4,0,4,function_mir_unit_type_code(),function_mir_mode_value(),-1,0,0));
  vec_push<MirFunctionRecord>(first,function_mir_return(0,4,-1,0));
  var second:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,3);
  vec_push<MirFunctionRecord>(second,function_mir_callable_header(4,3,4,3,function_mir_unit_type_code(),function_mir_mode_value(),-1,0,1));
  vec_push<MirFunctionRecord>(second,function_mir_call(4,3,0,-1,0,4,function_mir_unit_type_code(),function_mir_mode_value(),0));
  vec_push<MirFunctionRecord>(second,function_mir_return(4,3,-1,1));
  var headers:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,2);
  vec_push<MirFunctionRecord>(headers,vec_get<MirFunctionRecord>(first,0));
  vec_push<MirFunctionRecord>(headers,vec_get<MirFunctionRecord>(second,0));
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,2);
  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));vec_push<MirCfgRecord>(cfg,cfg_return(0,-1));
  var first_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);
  var second_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,1);
  vec_push<MirPlacementRecord>(second_placements,mir_place(0,0,0));
  var features:Vec<i64>=vec_new<i64>(allocator,0);
  var prototypes:Buffer=buffer_new(allocator,64);var bodies:Buffer=buffer_new(allocator,256);
  var declarations:Buffer=buffer_new(allocator,64);var c_source:Buffer=buffer_new(allocator,512);
  var c_header:Buffer=buffer_new(allocator,128);
  let first_status:i32=canonical_c_append_scalar_function_with_catalog(source,first,headers,cfg,first_placements,prototypes,bodies,declarations,features);
  if(first_status!=0){return first_status;}
  let second_status:i32=canonical_c_append_scalar_function_with_catalog(source,second,headers,cfg,second_placements,prototypes,bodies,declarations,features);
  if(second_status!=0){return checked_add(100,second_status);}
  let source_status:i32=canonical_c_finish_scalar_module(prototypes,bodies,features,c_source);
  if(source_status!=0){return checked_add(200,source_status);}
  let header_status:i32=canonical_c_finish_public_header(declarations,c_header);
  if(header_status!=0){return checked_add(300,header_status);}
  print(buffer_len(c_source));var index:i64=0;
  while(index<buffer_len(c_source)){print(buffer_get(c_source,index));index=checked_add(index,1);}
  print(buffer_len(c_header));index=0;
  while(index<buffer_len(c_header)){print(buffer_get(c_header,index));index=checked_add(index,1);}
  drop(c_header);drop(c_source);drop(declarations);drop(bodies);drop(prototypes);
  drop(features);drop(second_placements);drop(first_placements);drop(cfg);drop(headers);
  drop(second);drop(first);drop(source);
 }
 return 0;
}
'''
CANONICAL_C_BOOL_MULTIFUNCTION_PROBE = CANONICAL_C_MULTIFUNCTION_PROBE.replace(
    "function_mir_i64_type_code()", "function_mir_bool_type_code()",
)

CANONICAL_C_JUMP_PROBE = CANONICAL_C_BACKEND_PROBE.replace(
    "vec_new<MirCfgRecord>(allocator,2);\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));vec_push<MirCfgRecord>(cfg,cfg_return(0,2));",
    "vec_new<MirCfgRecord>(allocator,4);\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));vec_push<MirCfgRecord>(cfg,cfg_jump(0,1));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(1,1));vec_push<MirCfgRecord>(cfg,cfg_return(1,2));",
)

CANONICAL_C_JUMP_TARGET_BODY_PROBE = CANONICAL_C_JUMP_PROBE.replace(
    "mir_place(0,3,3)", "mir_place(1,3,0)",
)

CANONICAL_C_UNREACHABLE_PROBE = CANONICAL_C_JUMP_PROBE.replace(
    "cfg_return(1,2)", "cfg_unreachable(1)",
)

CANONICAL_C_CALL_PROBE = CANONICAL_C_MULTIFUNCTION_PROBE.replace(
    "vec_new<MirFunctionRecord>(allocator,4);",
    "vec_new<MirFunctionRecord>(allocator,7);",
).replace(
    "  vec_push<MirFunctionRecord>(first,function_mir_return(5,1,0,0));",
    "  vec_push<MirFunctionRecord>(first,function_mir_temporary(1,function_mir_i64_type_code(),1));\n"
    "  vec_push<MirFunctionRecord>(first,function_mir_call(6,6,1,1,6,6,function_mir_i64_type_code(),function_mir_mode_value(),1));\n"
    "  vec_push<MirFunctionRecord>(first,function_mir_call_argument(1,0,function_mir_mode_value(),0));\n"
    "  vec_push<MirFunctionRecord>(first,function_mir_return(5,1,1,2));",
).replace(
    "vec_push<MirCfgRecord>(first_cfg,cfg_block(0,0));vec_push<MirCfgRecord>(first_cfg,cfg_return(0,0));",
    "vec_push<MirCfgRecord>(first_cfg,cfg_block(0,0));vec_push<MirCfgRecord>(first_cfg,cfg_return(0,1));",
).replace(
    "var first_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,1);\n"
    "  vec_push<MirPlacementRecord>(first_placements,mir_place(0,0,0));",
    "var first_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,2);\n"
    "  vec_push<MirPlacementRecord>(first_placements,mir_place(0,0,0));\n"
    "  vec_push<MirPlacementRecord>(first_placements,mir_place(0,1,1));",
).replace(
    "  var features:Vec<i64>=vec_new<i64>(allocator,0);",
    "  var headers:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,3);\n"
    "  vec_push<MirFunctionRecord>(headers,vec_get<MirFunctionRecord>(first,0));\n"
    "  vec_push<MirFunctionRecord>(headers,vec_get<MirFunctionRecord>(second,0));\n"
    "  vec_push<MirFunctionRecord>(headers,vec_get<MirFunctionRecord>(second,1));\n"
    "  var features:Vec<i64>=vec_new<i64>(allocator,0);",
).replace(
    "canonical_c_append_scalar_function(source,first,first_cfg",
    "canonical_c_append_scalar_function_with_catalog(source,first,headers,first_cfg",
).replace(
    "canonical_c_append_scalar_function(source,second,second_cfg",
    "canonical_c_append_scalar_function_with_catalog(source,second,headers,second_cfg",
).replace(
    "  drop(features);drop(second_placements);",
    "  drop(features);drop(headers);drop(second_placements);",
)

CANONICAL_C_I32_CALL_PROBE = CANONICAL_C_CALL_PROBE.replace(
    "function_mir_i64_type_code()", "function_mir_i32_type_code()",
)
CANONICAL_C_BOOL_CALL_PROBE = CANONICAL_C_CALL_PROBE.replace(
    "function_mir_i64_type_code()", "function_mir_bool_type_code()",
)

CANONICAL_C_EQUAL_PROBE = CANONICAL_C_BACKEND_PROBE.replace(
    "function_mir_temporary(2,function_mir_i64_type_code(),2)",
    "function_mir_temporary(2,function_mir_bool_type_code(),2)",
).replace(
    "function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy()",
    "function_mir_binary_equal_symbol(),function_mir_bool_type_code(),function_mir_exact_numeric_policy()",
).replace(
    "cfg_return(0,2)", "cfg_return(0,0)",
)

CANONICAL_C_BOOL_COMPARISON_PROBE = CANONICAL_C_EQUAL_PROBE.replace(
    "compute23", "compute10",
).replace(
    "function_mir_i64_type_code()", "function_mir_bool_type_code()",
)

CANONICAL_C_BRANCH_PROBE = CANONICAL_C_EQUAL_PROBE.replace(
    "vec_new<MirCfgRecord>(allocator,2);\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));vec_push<MirCfgRecord>(cfg,cfg_return(0,0));",
    "vec_new<MirCfgRecord>(allocator,6);\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));vec_push<MirCfgRecord>(cfg,cfg_branch(0,2,1,2));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(1,1));vec_push<MirCfgRecord>(cfg,cfg_return(1,0));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(2,2));vec_push<MirCfgRecord>(cfg,cfg_return(2,1));",
)

CANONICAL_C_BRANCH_ARM_BODY_PROBES = (
    CANONICAL_C_BRANCH_PROBE.replace("mir_place(0,3,3)", "mir_place(1,3,0)"),
    CANONICAL_C_BRANCH_PROBE.replace("mir_place(0,3,3)", "mir_place(2,3,0)"),
)

CANONICAL_C_JOIN_PROBE = CANONICAL_C_BRANCH_ARM_BODY_PROBES[0].replace(
    "vec_new<MirCfgRecord>(allocator,6);",
    "vec_new<MirCfgRecord>(allocator,8);",
).replace(
    "cfg_return(1,0)", "cfg_jump(1,3)",
).replace(
    "vec_push<MirCfgRecord>(cfg,cfg_block(2,2));vec_push<MirCfgRecord>(cfg,cfg_return(2,1));",
    "vec_push<MirCfgRecord>(cfg,cfg_block(2,2));vec_push<MirCfgRecord>(cfg,cfg_jump(2,3));\n"
    "  vec_push<MirCfgRecord>(cfg,cfg_block(3,3));vec_push<MirCfgRecord>(cfg,cfg_return(3,0));",
)

CANONICAL_C_BACKEDGE_PROBE = CANONICAL_C_BRANCH_PROBE.replace(
    "cfg_return(1,0)", "cfg_jump(1,0)",
)

CANONICAL_C_SWITCH_PROBE = CANONICAL_C_BRANCH_PROBE.replace(
    "vec_new<MirCfgRecord>(allocator,6);",
    "vec_new<MirCfgRecord>(allocator,7);",
).replace(
    "vec_push<MirCfgRecord>(cfg,cfg_branch(0,2,1,2));",
    "vec_push<MirCfgRecord>(cfg,cfg_switch_case(0,0,2,1,0));"
    "vec_push<MirCfgRecord>(cfg,cfg_switch_default(0,0,2,1));",
)

CFG_MIR_PROBE = r'''module cfg_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;
import bootstrap_statement_semantics;

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
  var required:Vec<i64>=vec_new<i64>(allocator,0);
  var capability_catalog:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,0);
  var output:Buffer=buffer_new(allocator,256);
  let status:i32=materialize_bounded_cfg_canonical_mir(
   source,"demo",records,cfg,placements,required,capability_catalog,output
  );
  print(status);print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(capability_catalog);drop(required);drop(placements);drop(cfg);drop(records);drop(source);
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

CAPABLE_CFG_MIR_PROBE = PLACED_CFG_MIR_PROBE.replace(
    "vec_new<i64>(allocator,0);",
    "vec_new<i64>(allocator,1);vec_push<i64>(required,7);",
).replace(
    "vec_new<CapabilityCatalogEntry>(allocator,0);",
    "vec_new<CapabilityCatalogEntry>(allocator,1);\n"
    "  vec_push<CapabilityCatalogEntry>(capability_catalog,CapabilityCatalogEntry{capability_id:7,name_start:7,name_length:4});",
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

OWNERSHIP_BLOCK_MIR_PROBE = r'''module ownership_block_mir_probe
import bootstrap_mir_ownership_flow;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  var ownership:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,2);
  vec_push<MirOwnershipRecord>(ownership,ownership_record(
   ownership_record_kind_move(),0,1,2,0,0,ownership_state_live(),ownership_state_moved()
  ));
  vec_push<MirOwnershipRecord>(ownership,ownership_record(
   ownership_record_kind_implicit_drop(),1,2,ownership_record_no_other_binding_id(),1,1,
   ownership_state_live(),ownership_state_dropped()
  ));
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,3);
  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{
   global_id:0,source_kind:assembly_source_body_kind(),source_id:0,
   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),
   result:0,left:assembly_source_absent_record_value(),right:assembly_source_absent_record_value()
  });
  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{
   global_id:1,source_kind:assembly_source_ownership_kind(),source_id:0,
   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),
   result:1,left:0,right:assembly_source_absent_record_value()
  });
  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{
   global_id:2,source_kind:assembly_source_ownership_kind(),source_id:1,
   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),
   result:assembly_source_absent_record_value(),left:1,right:assembly_source_absent_record_value()
  });
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,3);
  vec_push<MirPlacementRecord>(placements,mir_place(0,0,0));
  vec_push<MirPlacementRecord>(placements,mir_place(0,1,1));
  vec_push<MirPlacementRecord>(placements,mir_place(0,2,2));
  var output:Buffer=buffer_new(allocator,256);
  print(materialize_canonical_ownership_block_instructions(ownership,sources,placements,0,output));
  print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  var invalid_sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,1);
  vec_push<MirFunctionInstructionSource>(invalid_sources,MirFunctionInstructionSource{
   global_id:0,source_kind:assembly_source_ownership_kind(),source_id:0,
   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),
   result:1,left:9,right:assembly_source_absent_record_value()
  });
  var invalid_placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,1);
  vec_push<MirPlacementRecord>(invalid_placements,mir_place(0,0,0));
  var rejected:Buffer=buffer_new(allocator,32);
  print(materialize_canonical_ownership_block_instructions(
   ownership,invalid_sources,invalid_placements,0,rejected
  ));
  drop(rejected);drop(invalid_placements);drop(invalid_sources);drop(output);drop(placements);drop(sources);drop(ownership);
  return 0;
 }
}
'''

SOURCED_OWNERSHIP_CFG_MIR_PROBE = r'''module sourced_ownership_cfg_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_assembly_plan;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_bundle;
import bootstrap_statement_semantics;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"module demo\nfn compute()->unit { let item:Buffer; return 1; }\n");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,4);
  vec_push<MirFunctionRecord>(records,function_mir_header(12,49,15,7,function_mir_unit_type_code()));
  vec_push<MirFunctionRecord>(records,function_mir_source_local(37,4,0,function_mir_buffer_type_code(),7,1));
  vec_push<MirFunctionRecord>(records,function_mir_const(57,1,0,0,function_mir_buffer_type_code(),0));
  vec_push<MirFunctionRecord>(records,function_mir_return(50,9,-1,0));
  var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,1);
  vec_push<MirFunctionContractRecord>(contracts,MirFunctionContractRecord{
   kind:function_contract_const_kind(),clause_ordinal:0,contract_kind:function_contract_precondition_phase(),
   start:57,length:1,id:0,result:0,left:-1,right:-1,symbol:0,
   type_code:function_mir_buffer_type_code(),numeric_policy:0
  });
  var contract_locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,0);
  var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,1);
  vec_push<MirOwnershipBinding>(bindings,ownership_binding_with_drop(7,0,1,1,1));
  var ownership:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,1);
  vec_push<MirOwnershipRecord>(ownership,ownership_record(
   ownership_record_kind_implicit_drop(),0,7,ownership_record_no_other_binding_id(),0,1,
   ownership_state_live(),ownership_state_dropped()
  ));
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,3);
  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{
   global_id:0,source_kind:assembly_source_contract_record_kind(),source_id:0,
   contract_kind:function_contract_precondition_phase(),clause_ordinal:0,
   result:0,left:assembly_source_absent_record_value(),right:assembly_source_absent_record_value()
  });
  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{
   global_id:1,source_kind:assembly_source_body_kind(),source_id:0,
   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),
   result:0,left:assembly_source_absent_record_value(),right:assembly_source_absent_record_value()
  });
  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{
   global_id:2,source_kind:assembly_source_ownership_kind(),source_id:0,
   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),
   result:assembly_source_absent_record_value(),left:0,right:assembly_source_absent_record_value()
  });
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,2);
  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));
  vec_push<MirCfgRecord>(cfg,cfg_return_unit(0));
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,3);
  vec_push<MirPlacementRecord>(placements,mir_place(0,0,0));
  vec_push<MirPlacementRecord>(placements,mir_place(0,1,1));
  vec_push<MirPlacementRecord>(placements,mir_place(0,2,2));
  var required:Vec<i64>=vec_new<i64>(allocator,0);
  var capability_catalog:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,0);
  var output:Buffer=buffer_new(allocator,512);
  let status:i32=materialize_sourced_cfg_canonical_mir(
   source,"demo",records,contracts,contract_locals,bindings,ownership,sources,cfg,placements,required,capability_catalog,output
  );
  print(status);print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(capability_catalog);drop(required);drop(placements);drop(cfg);
  drop(sources);drop(ownership);drop(bindings);drop(contract_locals);drop(contracts);drop(records);drop(source);
  return status;
 }
}
'''

INVALID_SOURCED_OWNERSHIP_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "ownership_binding_with_drop(7,0,1,1,1)",
    "ownership_binding_with_drop(8,0,1,1,1)",
).replace("return status;", "return 0;")

INVALID_SOURCED_CONTRACT_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "contract_kind:function_contract_precondition_phase(),clause_ordinal:0,\n"
    "   result:0,left:assembly_source_absent_record_value()",
    "contract_kind:function_contract_postcondition_phase(),clause_ordinal:0,\n"
    "   result:0,left:assembly_source_absent_record_value()",
).replace("return status;", "return 0;")

SOURCED_BINARY_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "function_mir_const(57,1,0,0,function_mir_buffer_type_code(),0)",
    "function_mir_binary(57,1,0,0,0,0,1,function_mir_buffer_type_code(),function_mir_exact_numeric_policy(),0)",
)

SOURCED_COPY_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "function_mir_const(57,1,0,0,function_mir_buffer_type_code(),0)",
    "function_mir_copy(57,1,0,0,0,7,0)",
)

SOURCED_PRINT_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "function_mir_const(57,1,0,0,function_mir_buffer_type_code(),0)",
    "function_mir_print(57,1,0,0,0)",
)

SOURCED_CALL_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "function_mir_const(57,1,0,0,function_mir_buffer_type_code(),0)",
    "function_mir_call(57,1,0,0,15,7,function_mir_buffer_type_code(),function_mir_mode_value(),0)",
)

SOURCED_CALL_ARGUMENT_CFG_MIR_PROBE = SOURCED_CALL_CFG_MIR_PROBE.replace(
    "vec_new<MirFunctionRecord>(allocator,4)",
    "vec_new<MirFunctionRecord>(allocator,5)",
).replace(
    "vec_push<MirFunctionRecord>(records,function_mir_return(50,9,-1,0));",
    "vec_push<MirFunctionRecord>(records,function_mir_call_argument(0,0,function_mir_mode_value(),0));\n"
    "  vec_push<MirFunctionRecord>(records,function_mir_return(50,9,-1,0));",
)

def _sourced_body_probe(record: str) -> str:
    return SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
        "function_mir_const(57,1,0,0,function_mir_buffer_type_code(),0)", record,
    )


SOURCED_ENUM_CONSTRUCT_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_construct(57,1,0,0,-1,2,function_mir_copy_payload_enum_type_code(0),0)"
)
SOURCED_ENUM_TAG_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_enum_tag_load(57,1,0,0,0,0)"
)
SOURCED_ENUM_PAYLOAD_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_enum_payload_load(57,1,0,0,0,2,0)"
)
SOURCED_STRUCT_CONSTRUCT_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_struct_construct(57,1,0,0,0,2,function_mir_i64_struct_type_code(0),0)"
)
SOURCED_STRUCT_LOAD_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_struct_field_load(57,1,0,0,0,2,0)"
)
SOURCED_STRUCT_STORE_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_struct_field_store(57,1,0,0,0,2,function_mir_i64_struct_type_code(0),0)"
)
SOURCED_STRUCT_REPLACE_CFG_MIR_PROBE = _sourced_body_probe(
    "function_mir_struct_field_replace(57,1,0,0,0,2,function_mir_i64_struct_type_code(0),0)"
)

SOURCED_TWO_BODY_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "vec_new<MirFunctionRecord>(allocator,4)", "vec_new<MirFunctionRecord>(allocator,5)",
).replace(
    "vec_push<MirFunctionRecord>(records,function_mir_return(50,9,-1,0));",
    "vec_push<MirFunctionRecord>(records,function_mir_print(57,1,1,0,1));\n"
    "  vec_push<MirFunctionRecord>(records,function_mir_return(50,9,-1,0));",
).replace(
    "vec_new<MirFunctionInstructionSource>(allocator,3)", "vec_new<MirFunctionInstructionSource>(allocator,4)",
).replace(
    "global_id:2,source_kind:assembly_source_ownership_kind(),source_id:0,",
    "global_id:2,source_kind:assembly_source_body_kind(),source_id:1,\n"
    "   contract_kind:assembly_source_no_contract_phase(),clause_ordinal:assembly_source_absent_record_value(),\n"
    "   result:-1,left:assembly_source_absent_record_value(),right:assembly_source_absent_record_value()\n"
    "  });\n  vec_push<MirFunctionInstructionSource>(sources,MirFunctionInstructionSource{\n"
    "   global_id:3,source_kind:assembly_source_ownership_kind(),source_id:0,",
).replace(
    "vec_new<MirPlacementRecord>(allocator,3)", "vec_new<MirPlacementRecord>(allocator,4)",
).replace(
    "vec_push<MirPlacementRecord>(placements,mir_place(0,2,2));",
    "vec_push<MirPlacementRecord>(placements,mir_place(0,2,2));\n"
    "  vec_push<MirPlacementRecord>(placements,mir_place(0,3,3));",
)

SOURCED_MULTIPLE_LOCALS_CFG_MIR_PROBE = SOURCED_TWO_BODY_CFG_MIR_PROBE.replace(
    "vec_new<MirFunctionRecord>(allocator,5)", "vec_new<MirFunctionRecord>(allocator,6)",
).replace(
    "vec_push<MirFunctionRecord>(records,function_mir_source_local(37,4,0,function_mir_buffer_type_code(),7,1));",
    "vec_push<MirFunctionRecord>(records,function_mir_source_local(37,4,0,function_mir_buffer_type_code(),7,1));\n"
    "  vec_push<MirFunctionRecord>(records,function_mir_temporary(1,function_mir_i64_type_code(),1));",
)

SOURCED_PARAMETER_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "function_mir_header(12,49,15,7,function_mir_unit_type_code())",
    "function_mir_callable_header(12,49,15,7,function_mir_buffer_type_code(),function_mir_mode_borrowed(),0,1,1)",
).replace(
    "function_mir_source_local(37,4,0,function_mir_buffer_type_code(),7,1)",
    "function_mir_parameter(37,4,0,function_mir_buffer_type_code(),7,1,function_mir_mode_borrowed(),0)",
)

SOURCED_CONTRACT_LOCAL_CFG_MIR_PROBE = SOURCED_OWNERSHIP_CFG_MIR_PROBE.replace(
    "var contract_locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,0);",
    "var contract_locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,1);\n"
    "  vec_push<MirFunctionContractLocal>(contract_locals,MirFunctionContractLocal{\n"
    "   local_id:1,source_local_id:10,type_code:function_mir_i64_type_code(),\n"
    "   contract_kind:function_contract_precondition_phase(),clause_ordinal:0\n"
    "  });",
)

CONTRACT_INSTRUCTION_CATALOG_PROBE = r'''module contract_instruction_catalog_probe
import bootstrap_mir_functions;
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn emit_one(
 borrow source:Buffer,record:MirFunctionContractRecord,provenance:MirFunctionInstructionSource
)->i32
requires_caps [allocate]
{
 let allocator:Allocator=system_allocator();var output:Buffer=buffer_new(allocator,192);
 let status:i32=materialize_canonical_contract_instruction(source,record,provenance,output);
 print(status);print(buffer_len(output));var index:i64=0;
 while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
 drop(output);return status;
}

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();let source:Buffer=buffer_from_string(allocator,"1");
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_const_kind(),clause_ordinal:0,contract_kind:function_contract_precondition_phase(),
   start:0,length:1,id:0,result:0,left:-1,right:-1,symbol:0,type_code:1,numeric_policy:0
  },MirFunctionInstructionSource{global_id:0,source_kind:assembly_source_contract_record_kind(),source_id:0,
   contract_kind:function_contract_precondition_phase(),clause_ordinal:0,result:0,left:-1,right:-1}));
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_binary_kind(),clause_ordinal:0,contract_kind:function_contract_precondition_phase(),
   start:0,length:1,id:1,result:0,left:0,right:0,symbol:1,type_code:1,numeric_policy:function_mir_exact_numeric_policy()
  },MirFunctionInstructionSource{global_id:1,source_kind:assembly_source_contract_record_kind(),source_id:1,
   contract_kind:function_contract_precondition_phase(),clause_ordinal:0,result:0,left:0,right:0}));
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_check_kind(),clause_ordinal:0,contract_kind:function_contract_postcondition_phase(),
   start:0,length:1,id:2,result:-1,left:0,right:-1,symbol:0,type_code:2,numeric_policy:0
  },MirFunctionInstructionSource{global_id:2,source_kind:assembly_source_contract_record_kind(),source_id:2,
   contract_kind:function_contract_postcondition_phase(),clause_ordinal:0,result:-1,left:0,right:-1}));
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_call_kind(),clause_ordinal:0,contract_kind:function_contract_precondition_phase(),
   start:0,length:1,id:3,result:0,left:0,right:-1,symbol:13,type_code:1,numeric_policy:0
  },MirFunctionInstructionSource{global_id:3,source_kind:assembly_source_contract_record_kind(),source_id:3,
   contract_kind:function_contract_precondition_phase(),clause_ordinal:0,result:0,left:0,right:-1}));
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_result_capture_kind(),clause_ordinal:0,contract_kind:function_contract_postcondition_phase(),
   start:0,length:1,id:4,result:0,left:-1,right:-1,symbol:0,type_code:1,numeric_policy:0
  },MirFunctionInstructionSource{global_id:4,source_kind:assembly_source_contract_record_kind(),source_id:4,
   contract_kind:function_contract_postcondition_phase(),clause_ordinal:0,result:0,left:0,right:-1}));
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_field_load_kind(),clause_ordinal:0,contract_kind:function_contract_postcondition_phase(),
   start:0,length:1,id:5,result:0,left:0,right:-1,symbol:2,type_code:1,numeric_policy:0
  },MirFunctionInstructionSource{global_id:5,source_kind:assembly_source_contract_record_kind(),source_id:5,
   contract_kind:function_contract_postcondition_phase(),clause_ordinal:0,result:0,left:0,right:-1}));
  print(emit_one(source,MirFunctionContractRecord{
   kind:function_contract_old_snapshot_kind(),clause_ordinal:0,contract_kind:function_contract_entry_snapshot_phase(),
   start:0,length:1,id:6,result:0,left:0,right:-1,symbol:0,type_code:1,numeric_policy:0
  },MirFunctionInstructionSource{global_id:6,source_kind:assembly_source_contract_record_kind(),source_id:6,
   contract_kind:function_contract_entry_snapshot_phase(),clause_ordinal:0,result:0,left:0,right:-1}));
  drop(source);return 0;
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

CAPABILITY_JSON_PROBE = r'''module capability_json_probe
import bootstrap_statement_semantics;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"allocate io");
  var catalog:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,2);
  vec_push<CapabilityCatalogEntry>(catalog,CapabilityCatalogEntry{capability_id:7,name_start:0,name_length:8});
  vec_push<CapabilityCatalogEntry>(catalog,CapabilityCatalogEntry{capability_id:8,name_start:9,name_length:2});
  var required:Vec<i64>=vec_new<i64>(allocator,2);vec_push<i64>(required,7);vec_push<i64>(required,8);
  var output:Buffer=buffer_new(allocator,32);
  print(materialize_canonical_capabilities(source,required,catalog,output));print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  vec_push<i64>(required,7);
  print(materialize_canonical_capabilities(source,required,catalog,output));
  drop(output);drop(required);drop(catalog);drop(source);return 0;
 }
}
'''

CALLABLE_MIR_PROBE = r'''module callable_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"identity value");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,3);
  vec_push<MirFunctionRecord>(records,function_mir_callable_header(0,14,0,8,1,1,0,1,1));
  vec_push<MirFunctionRecord>(records,function_mir_parameter(9,5,0,1,7,0,1,0));
  vec_push<MirFunctionRecord>(records,function_mir_return(0,1,0,0));
  var output:Buffer=buffer_new(allocator,256);
  print(materialize_straight_line_canonical_mir(source,"demo",records,output));print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(records);drop(source);return 0;
 }
}
'''

CALL_MIR_PROBE = r'''module call_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"caller callee arg");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,6);
  vec_push<MirFunctionRecord>(records,function_mir_callable_header(0,17,0,6,1,0,-1,1,0));
  vec_push<MirFunctionRecord>(records,function_mir_parameter(14,3,0,1,7,0,0,0));
  vec_push<MirFunctionRecord>(records,function_mir_temporary_mode(1,1,0,0));
  vec_push<MirFunctionRecord>(records,function_mir_call(7,6,0,1,7,6,1,0,1));
  vec_push<MirFunctionRecord>(records,function_mir_call_argument(0,0,0,0));
  vec_push<MirFunctionRecord>(records,function_mir_return(0,1,1,2));
  var output:Buffer=buffer_new(allocator,384);
  print(materialize_straight_line_canonical_mir(source,"demo",records,output));print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(records);drop(source);return 0;
 }
}
'''

BORROWED_TEMP_MIR_PROBE = r'''module borrowed_temp_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"identity value");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,4);
  vec_push<MirFunctionRecord>(records,function_mir_callable_header(0,14,0,8,1,1,0,1,0));
  vec_push<MirFunctionRecord>(records,function_mir_parameter(9,5,0,1,7,0,1,0));
  vec_push<MirFunctionRecord>(records,function_mir_temporary_mode(1,1,0,1));
  vec_push<MirFunctionRecord>(records,function_mir_return(0,1,1,0));
  var output:Buffer=buffer_new(allocator,320);
  print(materialize_straight_line_canonical_mir(source,"demo",records,output));print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  drop(output);drop(records);drop(source);return 0;
 }
}
'''

OWNED_SOURCE_LOCAL_MIR_PROBE = r'''module owned_source_local_mir_probe
import bootstrap_mir_functions;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_resolved_source_function_bundle;

capability allocate;

fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"owned item");
  var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,3);
  vec_push<MirFunctionRecord>(records,function_mir_callable_header(0,10,0,5,14,0,-1,0,0));
  vec_push<MirFunctionRecord>(records,function_mir_source_local(6,4,0,4,7,1));
  vec_push<MirFunctionRecord>(records,function_mir_return(0,1,-1,0));
  var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,1);
  vec_push<MirOwnershipBinding>(bindings,ownership_binding_with_drop(7,0,1,1,1));
  var output:Buffer=buffer_new(allocator,320);
  print(materialize_bound_straight_line_canonical_mir(source,"demo",records,bindings,output));
  print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  var invalid_bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,1);
  vec_push<MirOwnershipBinding>(invalid_bindings,ownership_binding_with_drop(7,1,1,1,1));
  var rejected:Buffer=buffer_new(allocator,32);
  print(materialize_bound_straight_line_canonical_mir(source,"demo",records,invalid_bindings,rejected));
  drop(rejected);drop(invalid_bindings);drop(output);drop(bindings);drop(records);drop(source);return 0;
 }
}
'''


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


def test_merit_assembles_multiple_canonical_functions_without_python(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_PROJECT_ASSEMBLY_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-project-assembly")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    actual = bytes(values[1:]).decode("utf-8")
    assert values[0] == len(actual.encode("utf-8"))
    assert actual == (
        '{"functions":[{"name":"first"},{"name":"second"}],'
        '"name":"demo","schema":"bootstrap-mir-v1"}'
    )


def test_merit_scalar_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_C_BACKEND_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-backend")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), tuple(MirLocal(i, f"_t{i}", MirType("i64")) for i in range(3)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=2, ownership="value"),
            MirInstruction(1, "const", result=1, value=3, ownership="value"),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="checked"),
            MirInstruction(3, "print", operands=(2,)),
        ), MirTerminator("return", operands=(2,))),), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("probe", "type_name"),
    [
        (CANONICAL_C_MULTIFUNCTION_PROBE, "i64"),
        (CANONICAL_C_I32_MULTIFUNCTION_PROBE, "i32"),
        (CANONICAL_C_BOOL_MULTIFUNCTION_PROBE, "bool"),
    ],
)
def test_merit_multifunction_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, probe: str, type_name: str,
) -> None:
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-multifunction")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (
        MirFunction("first", MirType(type_name), (MirLocal(0, "_t0", MirType(type_name)),),
                    (MirBlock(0, (MirInstruction(0, "const", result=0, value=1),),
                              MirTerminator("return", operands=(0,))),), 0),
        MirFunction("second", MirType(type_name), (MirLocal(0, "value", MirType(type_name)),),
                    (MirBlock(0, (), MirTerminator("return", operands=(0,))),), 0,
                    parameters=(MirParameter(0),), exported=True),
    ))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_scalar_jump_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_C_JUMP_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-jump")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), tuple(MirLocal(i, f"_t{i}", MirType("i64")) for i in range(3)),
        (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="checked"),
                MirInstruction(3, "print", operands=(2,)),
            ), MirTerminator("jump", targets=(1,))),
            MirBlock(1, (), MirTerminator("return", operands=(2,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_scalar_jump_target_body_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    assert "mir_place(1,3,0)" in CANONICAL_C_JUMP_TARGET_BODY_PROBE
    root = _project(tmp_path, CANONICAL_C_JUMP_TARGET_BODY_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-jump-target-body")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("i64")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="checked"),
            ), MirTerminator("jump", targets=(1,))),
            MirBlock(1, (
                MirInstruction(3, "print", operands=(2,)),
            ), MirTerminator("return", operands=(2,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_scalar_unreachable_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_C_UNREACHABLE_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-unreachable")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("i64")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="checked"),
                MirInstruction(3, "print", operands=(2,)),
            ), MirTerminator("jump", targets=(1,))),
            MirBlock(1, (), MirTerminator("unreachable")),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("placement", "status"),
    [("mir_place(2,3,0)", 87), ("mir_place(1,3,1)", 19)],
)
def test_merit_scalar_jump_target_body_rejects_invalid_placement(
    tmp_path: Path, placement: str, status: int,
) -> None:
    probe = CANONICAL_C_JUMP_TARGET_BODY_PROBE.replace("mir_place(1,3,0)", placement)
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-jump-target-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


@pytest.mark.parametrize(
    ("probe", "type_name"),
    [
        (CANONICAL_C_CALL_PROBE, "i64"),
        (CANONICAL_C_I32_CALL_PROBE, "i32"),
        (CANONICAL_C_BOOL_CALL_PROBE, "bool"),
    ],
)
def test_merit_scalar_call_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, probe: str, type_name: str,
) -> None:
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-call")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (
        MirFunction("first", MirType(type_name), (
            MirLocal(0, "_t0", MirType(type_name)), MirLocal(1, "_t1", MirType(type_name)),
        ), (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=1),
            MirInstruction(1, "call", result=1, operands=(0,), symbol="second"),
        ), MirTerminator("return", operands=(1,))),), 0),
        MirFunction("second", MirType(type_name), (MirLocal(0, "value", MirType(type_name)),),
                    (MirBlock(0, (), MirTerminator("return", operands=(0,))),), 0,
                    parameters=(MirParameter(0),), exported=True),
    ))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)
    generated_c = tmp_path / "call.c"
    generated_h = tmp_path / "call.h"
    driver_c = tmp_path / "call_driver.c"
    generated_c.write_text(c_source, encoding="utf-8", newline="\n")
    generated_h.write_text(c_header, encoding="utf-8", newline="\n")
    c_type = {"i32": "int32_t", "i64": "int64_t", "bool": "bool"}[type_name]
    call_check = "merit_second(false) == false" if type_name == "bool" else "merit_second(2) == 2"
    driver_c.write_text(
        f'#include "call.h"\n{c_type} first(void);\n'
        f'int main(void) {{ return first() == 1 && {call_check} ? 0 : 1; }}\n',
        encoding="utf-8", newline="\n",
    )
    cc = shutil.which("cc") or shutil.which("gcc")
    assert cc is not None
    program = tmp_path / "call-program"
    subprocess.run(
        [cc, "-std=c11", str(generated_c), str(driver_c), "-o", str(program)],
        check=True, text=True, capture_output=True,
    )
    result = subprocess.run([str(program)], check=True, text=True, capture_output=True)
    assert result.stdout == ""


def test_merit_scalar_call_c_backend_rejects_unknown_target(tmp_path: Path) -> None:
    probe = CANONICAL_C_CALL_PROBE.replace(
        "function_mir_call(6,6,1,1,6,6,",
        "function_mir_call(6,6,1,1,0,6,",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-call-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == 65
    assert native.stdout == ""


def test_merit_scalar_call_c_backend_rejects_borrowed_callee_parameter(tmp_path: Path) -> None:
    probe = CANONICAL_C_CALL_PROBE.replace(
        "function_mir_parameter(6,6,0,function_mir_i64_type_code(),0,0,function_mir_mode_value(),0)",
        "function_mir_parameter(6,6,0,function_mir_i64_type_code(),0,0,function_mir_mode_borrowed(),0)",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-call-borrowed-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == 74
    assert native.stdout == ""


@pytest.mark.parametrize(
    ("probe", "status"),
    [
        (
            CANONICAL_C_I32_MULTIFUNCTION_PROBE.replace(
                "function_mir_const(5,1,0,0,function_mir_i32_type_code(),0)",
                "function_mir_const(5,1,0,0,function_mir_i64_type_code(),0)",
            ),
            97,
        ),
        (
            CANONICAL_C_I32_CALL_PROBE.replace(
                "function_mir_parameter(6,6,0,function_mir_i32_type_code(),0,0",
                "function_mir_parameter(6,6,0,function_mir_i64_type_code(),0,0",
            ),
            96,
        ),
    ],
)
def test_merit_i32_scalar_c_backend_rejects_mixed_width_records(
    tmp_path: Path, probe: str, status: int,
) -> None:
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-i32-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


def test_merit_bool_scalar_c_backend_rejects_non_boolean_literal(tmp_path: Path) -> None:
    probe = CANONICAL_C_BOOL_MULTIFUNCTION_PROBE.replace("first1second", "first2second")
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-bool-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == 100
    assert native.stdout == ""


@pytest.mark.parametrize(("record_symbol", "mir_symbol"), [
    ("function_mir_binary_equal_symbol()", "=="),
    ("function_mir_binary_not_equal_symbol()", "!="),
])
def test_merit_bool_comparison_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, record_symbol: str, mir_symbol: str,
) -> None:
    probe = CANONICAL_C_BOOL_COMPARISON_PROBE.replace(
        "function_mir_binary_equal_symbol()", record_symbol,
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-bool-comparison")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("bool"), tuple(MirLocal(i, f"_t{i}", MirType("bool")) for i in range(3)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=True, ownership="value"),
            MirInstruction(1, "const", result=1, value=False, ownership="value"),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol=mir_symbol, numeric_policy="exact"),
            MirInstruction(3, "print", operands=(2,)),
        ), MirTerminator("return", operands=(0,))),), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_bool_ordering_c_backend_fails_closed(tmp_path: Path) -> None:
    probe = CANONICAL_C_BOOL_COMPARISON_PROBE.replace(
        "function_mir_binary_equal_symbol()", "function_mir_binary_greater_symbol()",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-bool-order-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == 98
    assert native.stdout == ""


@pytest.mark.parametrize("spelling", ("true", "false"))
def test_merit_textual_bool_constant_c_backend_matches_oracle(
    tmp_path: Path, spelling: str,
) -> None:
    second_start = 5 + len(spelling)
    probe = CANONICAL_C_BOOL_MULTIFUNCTION_PROBE.replace(
        "first1second", f"first{spelling}second",
    ).replace(
        "function_mir_const(5,1,0,0", f"function_mir_const(5,{len(spelling)},0,0",
    ).replace(
        "function_mir_callable_header(6,6,6,6",
        f"function_mir_callable_header({second_start},6,{second_start},6",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-textual-bool")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    module = MirModule("demo", (
        MirFunction("first", MirType("bool"), (MirLocal(0, "_t0", MirType("bool")),),
                    (MirBlock(0, (MirInstruction(0, "const", result=0, value=spelling == "true"),),
                              MirTerminator("return", operands=(0,))),), 0),
        MirFunction("second", MirType("bool"), (MirLocal(0, "value", MirType("bool")),),
                    (MirBlock(0, (), MirTerminator("return", operands=(0,))),), 0,
                    parameters=(MirParameter(0),), exported=True),
    ))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("record_symbol", "mir_symbol", "type_name"),
    [
        ("function_mir_binary_equal_symbol()", "==", "i64"),
        ("function_mir_binary_not_equal_symbol()", "!=", "i64"),
        ("function_mir_binary_greater_equal_symbol()", ">=", "i64"),
        ("function_mir_binary_less_equal_symbol()", "<=", "i64"),
        ("function_mir_binary_greater_symbol()", ">", "i64"),
        ("function_mir_binary_less_symbol()", "<", "i64"),
        ("function_mir_binary_equal_symbol()", "==", "i32"),
    ],
)
def test_merit_scalar_comparison_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, record_symbol: str, mir_symbol: str, type_name: str,
) -> None:
    probe = CANONICAL_C_EQUAL_PROBE.replace("function_mir_binary_equal_symbol()", record_symbol)
    if type_name == "i32":
        probe = probe.replace("function_mir_i64_type_code()", "function_mir_i32_type_code()")
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-equality")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType(type_name), (
            MirLocal(0, "_t0", MirType(type_name)), MirLocal(1, "_t1", MirType(type_name)),
            MirLocal(2, "_t2", MirType("bool")),
        ), (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=2, ownership="value"),
            MirInstruction(1, "const", result=1, value=3, ownership="value"),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol=mir_symbol, numeric_policy="exact"),
            MirInstruction(3, "print", operands=(2,)),
        ), MirTerminator("return", operands=(0,))),), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("probe", "status"),
    [
        (
            CANONICAL_C_EQUAL_PROBE.replace(
                "function_mir_bool_type_code(),function_mir_exact_numeric_policy()",
                "function_mir_bool_type_code(),function_mir_checked_numeric_policy()",
            ),
            76,
        ),
        (
            CANONICAL_C_EQUAL_PROBE.replace(
                "function_mir_temporary(2,function_mir_bool_type_code(),2)",
                "function_mir_temporary(2,function_mir_i64_type_code(),2)",
            ),
            77,
        ),
    ],
)
def test_merit_scalar_comparison_c_backend_rejects_invalid_shape(
    tmp_path: Path, probe: str, status: int,
) -> None:
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-comparison-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


def test_merit_scalar_branch_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    assert "cfg_branch(0,2,1,2)" in CANONICAL_C_BRANCH_PROBE
    root = _project(tmp_path, CANONICAL_C_BRANCH_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-branch")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("bool")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="==", numeric_policy="exact"),
                MirInstruction(3, "print", operands=(2,)),
            ), MirTerminator("branch", operands=(2,), targets=(1, 2))),
            MirBlock(1, (), MirTerminator("return", operands=(0,))),
            MirBlock(2, (), MirTerminator("return", operands=(1,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize("arm", (1, 2))
def test_merit_scalar_branch_arm_body_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, arm: int,
) -> None:
    probe = CANONICAL_C_BRANCH_ARM_BODY_PROBES[arm - 1]
    assert f"mir_place({arm},3,0)" in probe
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-branch-arm-body")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    print_instruction = MirInstruction(3, "print", operands=(2,))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("bool")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="==", numeric_policy="exact"),
            ), MirTerminator("branch", operands=(2,), targets=(1, 2))),
            MirBlock(1, (print_instruction,) if arm == 1 else (), MirTerminator("return", operands=(0,))),
            MirBlock(2, (print_instruction,) if arm == 2 else (), MirTerminator("return", operands=(1,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("placement", "status"),
    [("mir_place(3,3,0)", 87), ("mir_place(1,3,1)", 19)],
)
def test_merit_scalar_branch_arm_body_rejects_invalid_placement(
    tmp_path: Path, placement: str, status: int,
) -> None:
    probe = CANONICAL_C_BRANCH_ARM_BODY_PROBES[0].replace("mir_place(1,3,0)", placement)
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-branch-arm-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


def test_merit_scalar_four_block_join_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    assert "cfg_jump(2,3)" in CANONICAL_C_JOIN_PROBE
    root = _project(tmp_path, CANONICAL_C_JOIN_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-join")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("bool")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="==", numeric_policy="exact"),
            ), MirTerminator("branch", operands=(2,), targets=(1, 2))),
            MirBlock(1, (MirInstruction(3, "print", operands=(2,)),), MirTerminator("jump", targets=(3,))),
            MirBlock(2, (), MirTerminator("jump", targets=(3,))),
            MirBlock(3, (), MirTerminator("return", operands=(0,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("old", "new", "status"),
    [
        ("cfg_jump(2,3)", "cfg_jump(2,4)", 27),
        ("cfg_branch(0,2,1,2)", "cfg_branch(0,0,1,2)", 86),
        ("mir_place(1,3,0)", "mir_place(1,2,0)", 88),
        ("cfg_return(3,0)", "cfg_return(3,2)", 89),
    ],
)
def test_merit_scalar_general_cfg_rejects_invalid_shape(
    tmp_path: Path, old: str, new: str, status: int,
) -> None:
    assert old in CANONICAL_C_JOIN_PROBE
    root = _project(tmp_path, CANONICAL_C_JOIN_PROBE.replace(old, new))
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-cfg-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


def test_merit_scalar_backedge_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    assert "cfg_jump(1,0)" in CANONICAL_C_BACKEDGE_PROBE
    root = _project(tmp_path, CANONICAL_C_BACKEDGE_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-backedge")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("bool")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="==", numeric_policy="exact"),
                MirInstruction(3, "print", operands=(2,)),
            ), MirTerminator("branch", operands=(2,), targets=(1, 2))),
            MirBlock(1, (), MirTerminator("jump", targets=(0,))),
            MirBlock(2, (), MirTerminator("return", operands=(1,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("source_literal", "expected_stdout"),
    [("compute23", ""), ("compute22", "1\n")],
)
def test_merit_scalar_join_generated_c_executes_both_paths(
    tmp_path: Path, source_literal: str, expected_stdout: str,
) -> None:
    probe = CANONICAL_C_JOIN_PROBE.replace("compute23", source_literal)
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    _, _, emitter = build(project, root / "build" / "canonical-c-join-emitter")
    encoded = subprocess.run([str(emitter)], check=True, text=True, capture_output=True).stdout
    values = [int(value) for value in encoded.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    generated_c = tmp_path / "generated.c"
    generated_h = tmp_path / "generated.h"
    driver_c = tmp_path / "driver.c"
    generated_c.write_text(c_source, encoding="utf-8", newline="\n")
    generated_h.write_text(c_header, encoding="utf-8", newline="\n")
    driver_c.write_text(
        '#include "generated.h"\nint main(void) { return merit_compute() == 2 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    cc = shutil.which("cc") or shutil.which("gcc")
    assert cc is not None
    executable = tmp_path / "generated-program"
    subprocess.run(
        [cc, "-std=c11", str(generated_c), str(driver_c), "-o", str(executable)],
        check=True, text=True, capture_output=True,
    )
    result = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
    assert result.stdout == expected_stdout


@pytest.mark.parametrize("case_value", (2, 7))
def test_merit_scalar_switch_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, case_value: int,
) -> None:
    probe = CANONICAL_C_SWITCH_PROBE.replace(
        "cfg_switch_case(0,0,2,1,0)", f"cfg_switch_case(0,0,{case_value},1,0)",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-switch")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), (
            MirLocal(0, "_t0", MirType("i64")), MirLocal(1, "_t1", MirType("i64")),
            MirLocal(2, "_t2", MirType("bool")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value=2, ownership="value"),
                MirInstruction(1, "const", result=1, value=3, ownership="value"),
                MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="==", numeric_policy="exact"),
                MirInstruction(3, "print", operands=(2,)),
            ), MirTerminator("switch", operands=(0,), targets=(1, 2), cases=(case_value,))),
            MirBlock(1, (), MirTerminator("return", operands=(0,))),
            MirBlock(2, (), MirTerminator("return", operands=(1,))),
        ), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)
    generated_c = tmp_path / "switch.c"
    generated_h = tmp_path / "switch.h"
    driver_c = tmp_path / "switch_driver.c"
    generated_c.write_text(c_source, encoding="utf-8", newline="\n")
    generated_h.write_text(c_header, encoding="utf-8", newline="\n")
    expected_return = 2 if case_value == 2 else 3
    driver_c.write_text(
        f'#include "switch.h"\nint main(void) {{ return merit_compute() == {expected_return} ? 0 : 1; }}\n',
        encoding="utf-8", newline="\n",
    )
    cc = shutil.which("cc") or shutil.which("gcc")
    assert cc is not None
    program = tmp_path / "switch-program"
    subprocess.run(
        [cc, "-std=c11", str(generated_c), str(driver_c), "-o", str(program)],
        check=True, text=True, capture_output=True,
    )
    result = subprocess.run([str(program)], check=True, text=True, capture_output=True)
    assert result.stdout == "0\n"


@pytest.mark.parametrize(
    ("probe", "status"),
    [
        (
            CANONICAL_C_SWITCH_PROBE.replace(
                "vec_push<MirCfgRecord>(cfg,cfg_switch_default(0,0,2,1));", "",
            ),
            92,
        ),
        (
            CANONICAL_C_SWITCH_PROBE.replace(
                "cfg_switch_default(0,0,2,1)", "cfg_switch_default(0,0,2,2)",
            ),
            91,
        ),
        (
            CANONICAL_C_SWITCH_PROBE.replace(
                "cfg_switch_default(0,0,2,1)", "cfg_switch_default(0,1,2,1)",
            ),
            90,
        ),
        (
            CANONICAL_C_SWITCH_PROBE.replace(
                "cfg_switch_case(0,0,2,1,0)", "cfg_switch_case(0,0,2,9,0)",
            ),
            27,
        ),
        (
            CANONICAL_C_SWITCH_PROBE.replace("cfg_switch_case(0,0,2,1,0)", "cfg_switch_case(0,2,2,1,0)")
            .replace("cfg_switch_default(0,0,2,1)", "cfg_switch_default(0,2,2,1)"),
            93,
        ),
        (
            CANONICAL_C_SWITCH_PROBE.replace(
                "vec_new<MirCfgRecord>(allocator,7)", "vec_new<MirCfgRecord>(allocator,8)",
            ).replace(
                "vec_push<MirCfgRecord>(cfg,cfg_switch_default(0,0,2,1));",
                "vec_push<MirCfgRecord>(cfg,cfg_switch_case(0,0,2,1,1));"
                "vec_push<MirCfgRecord>(cfg,cfg_switch_default(0,0,2,2));",
            ),
            94,
        ),
    ],
)
def test_merit_scalar_switch_c_backend_rejects_invalid_rows(
    tmp_path: Path, probe: str, status: int,
) -> None:
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-switch-rejected")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


@pytest.mark.parametrize(
    ("record_symbol", "mir_symbol"),
    [
        ("function_mir_binary_add_symbol()", "+"),
        ("function_mir_binary_subtract_symbol()", "-"),
        ("function_mir_binary_multiply_symbol()", "*"),
        ("function_mir_binary_divide_symbol()", "/"),
    ],
)
@pytest.mark.parametrize("type_name", ("i32", "i64"))
def test_merit_checked_scalar_c_backend_matches_python_oracle_bytes(
    tmp_path: Path, record_symbol: str, mir_symbol: str, type_name: str,
) -> None:
    probe = CANONICAL_C_BACKEND_PROBE.replace(
        "function_mir_binary_add_symbol()", record_symbol,
    )
    if type_name == "i32":
        probe = probe.replace("function_mir_i64_type_code()", "function_mir_i32_type_code()")
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-checked")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    header_length = values[1 + c_length]
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    assert header_length == len(c_header.encode("utf-8"))
    module = MirModule("demo", (MirFunction(
        "compute", MirType(type_name), tuple(MirLocal(i, f"_t{i}", MirType(type_name)) for i in range(3)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=2, ownership="value"),
            MirInstruction(1, "const", result=1, value=3, ownership="value"),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol=mir_symbol, numeric_policy="checked"),
            MirInstruction(3, "print", operands=(2,)),
        ), MirTerminator("return", operands=(2,))),), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_checked_i32_generated_c_executes(tmp_path: Path) -> None:
    probe = CANONICAL_C_BACKEND_PROBE.replace(
        "function_mir_i64_type_code()", "function_mir_i32_type_code()",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    _, _, emitter = build(project, root / "build" / "canonical-c-i32-checked-emitter")
    encoded = subprocess.run([str(emitter)], check=True, text=True, capture_output=True).stdout
    values = [int(value) for value in encoded.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    generated_c = tmp_path / "checked_i32.c"
    generated_h = tmp_path / "checked_i32.h"
    driver_c = tmp_path / "checked_i32_driver.c"
    generated_c.write_text(c_source, encoding="utf-8", newline="\n")
    generated_h.write_text(c_header, encoding="utf-8", newline="\n")
    driver_c.write_text(
        '#include "checked_i32.h"\nint main(void) { return merit_compute() == 5 ? 0 : 1; }\n',
        encoding="utf-8", newline="\n",
    )
    cc = shutil.which("cc") or shutil.which("gcc")
    assert cc is not None
    program = tmp_path / "checked-i32-program"
    subprocess.run(
        [cc, "-std=c11", str(generated_c), str(driver_c), "-o", str(program)],
        check=True, text=True, capture_output=True,
    )
    result = subprocess.run([str(program)], check=True, text=True, capture_output=True)
    assert result.stdout == "5\n"


@pytest.mark.parametrize(
    ("old", "new", "status"),
    [
        ("function_mir_binary(7,2,2,2,0,1,function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy(),2)",
         "function_mir_copy(7,2,2,2,99,0,2)", 101),
        ("function_mir_binary(7,2,2,2,0,1,function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy(),2)",
         "function_mir_copy(7,2,2,99,0,0,2)", 102),
        ("function_mir_binary(7,2,2,2,0,1,function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy(),2)",
         "function_mir_binary(7,2,2,2,99,1,function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy(),2)", 103),
        ("function_mir_print(7,2,3,2,3)", "function_mir_print(7,2,3,99,3)", 105),
    ],
)
def test_merit_scalar_backend_rejects_invalid_local_references(
    tmp_path: Path, old: str, new: str, status: int,
) -> None:
    assert old in CANONICAL_C_BACKEND_PROBE
    root = _project(tmp_path, CANONICAL_C_BACKEND_PROBE.replace(old, new))
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-invalid-local")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


def test_merit_scalar_backend_rejects_boolean_arithmetic(tmp_path: Path) -> None:
    probe = CANONICAL_C_BACKEND_PROBE.replace("compute23", "compute10")
    probe = probe.replace("function_mir_i64_type_code()", "function_mir_bool_type_code()")
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-bool-arithmetic")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == 104
    assert native.stdout == ""


def test_merit_scalar_copy_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    probe = CANONICAL_C_BACKEND_PROBE.replace(
        "function_mir_binary(7,2,2,2,0,1,function_mir_binary_add_symbol(),function_mir_i64_type_code(),function_mir_checked_numeric_policy(),2)",
        "function_mir_copy(7,2,2,2,0,0,2)",
    )
    root = _project(tmp_path, probe)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-copy")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted

    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    module = MirModule("demo", (MirFunction(
        "compute", MirType("i64"), tuple(MirLocal(i, f"_t{i}", MirType("i64")) for i in range(3)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=2, ownership="value"),
            MirInstruction(1, "const", result=1, value=3, ownership="value"),
            MirInstruction(2, "copy", result=2, operands=(0,)),
            MirInstruction(3, "print", operands=(2,)),
        ), MirTerminator("return", operands=(2,))),), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_unit_call_c_backend_matches_python_oracle_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_C_UNIT_CALL_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-unit-call")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    module = MirModule("demo", (
        MirFunction("ping", MirType("unit"), (),
                    (MirBlock(0, (), MirTerminator("return")),), 0),
        MirFunction("run", MirType("unit"), (),
                    (MirBlock(0, (MirInstruction(0, "call", symbol="ping"),),
                              MirTerminator("return")),), 0, exported=True),
    ))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


def test_merit_unit_call_generated_c_executes(tmp_path: Path) -> None:
    root = _project(tmp_path, CANONICAL_C_UNIT_CALL_PROBE)
    project = load_project(root / "Merit.toml")
    _, _, emitter = build(project, root / "build" / "canonical-c-unit-emitter")
    encoded = subprocess.run([str(emitter)], check=True, text=True, capture_output=True).stdout
    values = [int(value) for value in encoded.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    generated_c = tmp_path / "unit_call.c"
    generated_h = tmp_path / "unit_call.h"
    driver_c = tmp_path / "unit_call_driver.c"
    generated_c.write_text(c_source, encoding="utf-8", newline="\n")
    generated_h.write_text(c_header, encoding="utf-8", newline="\n")
    driver_c.write_text(
        '#include "unit_call.h"\nint main(void) { merit_run(); return 0; }\n',
        encoding="utf-8", newline="\n",
    )
    cc = shutil.which("cc") or shutil.which("gcc")
    assert cc is not None
    program = tmp_path / "unit-call-program"
    subprocess.run(
        [cc, "-std=c11", str(generated_c), str(driver_c), "-o", str(program)],
        check=True, text=True, capture_output=True,
    )
    assert subprocess.run([str(program)], check=True, capture_output=True).stdout == b""


@pytest.mark.parametrize(
    ("old", "new", "status"),
    [
        ("function_mir_call(4,3,0,-1,0,4,", "function_mir_call(4,3,0,0,0,4,", 160),
        ("cfg_return(0,-1)", "cfg_return(0,0)", 17),
    ],
)
def test_merit_unit_call_c_backend_rejects_invalid_result(
    tmp_path: Path, old: str, new: str, status: int,
) -> None:
    assert old in CANONICAL_C_UNIT_CALL_PROBE
    root = _project(tmp_path, CANONICAL_C_UNIT_CALL_PROBE.replace(old, new))
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-invalid-unit-call")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == status
    assert native.stdout == ""


def _scalar_literal_probe(literal: str, type_name: str) -> str:
    probe = CANONICAL_C_BACKEND_PROBE.replace("compute23", f"compute{literal}3")
    probe = probe.replace(
        "function_mir_const(7,1,0,0,", f"function_mir_const(7,{len(literal)},0,0,",
    ).replace(
        "function_mir_const(8,1,1,1,", f"function_mir_const({7 + len(literal)},1,1,1,",
    )
    if type_name == "i32":
        probe = probe.replace("function_mir_i64_type_code()", "function_mir_i32_type_code()")
    return probe


@pytest.mark.parametrize(
    ("literal", "type_name"),
    [("0002", "i32"), ("-2147483648", "i32"),
     ("0002", "i64"), ("-9223372036854775808", "i64")],
)
def test_merit_scalar_integer_literal_c_backend_matches_oracle_bytes(
    tmp_path: Path, literal: str, type_name: str,
) -> None:
    root = _project(tmp_path, _scalar_literal_probe(literal, type_name))
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "canonical-c-literal")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    c_length = values[0]
    c_source = bytes(values[1:1 + c_length]).decode("utf-8")
    c_header = bytes(values[2 + c_length:]).decode("utf-8")
    module = MirModule("demo", (MirFunction(
        "compute", MirType(type_name), tuple(MirLocal(i, f"_t{i}", MirType(type_name)) for i in range(3)),
        (MirBlock(0, (
            MirInstruction(0, "const", result=0, value=int(literal), ownership="value"),
            MirInstruction(1, "const", result=1, value=3, ownership="value"),
            MirInstruction(2, "binary", result=2, operands=(0, 1), symbol="+", numeric_policy="checked"),
            MirInstruction(3, "print", operands=(2,)),
        ), MirTerminator("return", operands=(2,))),), 0, exported=True,
    ),))
    from merit.bootstrap.mir_to_c import emit_c_header, emit_c_module
    assert c_source == emit_c_module(module)
    assert c_header == emit_c_header(module)


@pytest.mark.parametrize(
    ("literal", "type_name"),
    [("2147483648", "i32"), ("9223372036854775808", "i64"), ("00x2", "i64")],
)
def test_merit_scalar_integer_literal_c_backend_rejects_invalid_value(
    tmp_path: Path, literal: str, type_name: str,
) -> None:
    root = _project(tmp_path, _scalar_literal_probe(literal, type_name))
    project = load_project(root / "Merit.toml")
    assert interpret(project) == ""
    _, _, executable = build(project, root / "build" / "canonical-c-invalid-literal")
    native = subprocess.run([str(executable)], text=True, capture_output=True)
    assert native.returncode == 106
    assert native.stdout == ""


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


def test_cfg_materializer_includes_required_capabilities(tmp_path: Path) -> None:
    root = _project(tmp_path, CAPABLE_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "capable-cfg-mir")
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
        ), 0, ("demo",),
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


def test_merit_orders_ownership_effects_by_explicit_placement(tmp_path: Path) -> None:
    root = _project(tmp_path, OWNERSHIP_BLOCK_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "ownership-block-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    length = values[1]
    actual = bytes(values[2:2 + length]).decode("utf-8")
    expected = ",".join((
        json.dumps(MirInstruction(1, "move", result=1, operands=(0,), ownership="owned").to_data(), sort_keys=True, separators=(",", ":")),
        json.dumps(MirInstruction(2, "drop", operands=(1,), ownership="owned").to_data(), sort_keys=True, separators=(",", ":")),
    ))
    assert actual == expected
    assert values[2 + length] == 7


def test_merit_materializes_owned_local_and_drop_in_complete_cfg(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_OWNERSHIP_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-ownership-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value"),
                MirInstruction(2, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert values[1] == len(actual.encode("utf-8"))
    assert actual == expected


def test_merit_materializes_sourced_binary_in_complete_cfg(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_BINARY_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-binary-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "binary", result=0, operands=(0, 0), symbol="+", span=SourceSpan(57, 1), numeric_policy="exact"),
                MirInstruction(2, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert values[1] == len(actual.encode("utf-8"))
    assert actual == expected


def test_merit_materializes_sourced_copy_and_print_in_complete_cfg(tmp_path: Path) -> None:
    cases = (
        ("copy", SOURCED_COPY_CFG_MIR_PROBE, MirInstruction(1, "copy", result=0, operands=(0,), span=SourceSpan(57, 1))),
        ("print", SOURCED_PRINT_CFG_MIR_PROBE, MirInstruction(1, "print", operands=(0,), span=SourceSpan(57, 1))),
    )
    for name, probe, body_instruction in cases:
        root = _project(tmp_path / name, probe)
        project = load_project(root / "Merit.toml")
        interpreted = interpret(project)
        _, _, executable = build(project, root / "build" / f"sourced-{name}-cfg-mir")
        native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
        assert native == interpreted
        values = [int(value) for value in native.splitlines()]
        assert values[0] == 0
        actual = bytes(values[2:]).decode("utf-8")
        expected = canonical_mir_json(MirModule("demo", (MirFunction(
            "compute", MirType("unit"), (
                MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
            ), (
                MirBlock(0, (
                    MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                    body_instruction,
                    MirInstruction(2, "drop", operands=(0,), ownership="owned"),
                ), MirTerminator("return")),
            ), 0,
        ),)))
        assert values[1] == len(actual.encode("utf-8"))
        assert actual == expected


def test_merit_materializes_sourced_call_in_complete_cfg(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_CALL_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-call-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "call", result=0, symbol="compute", span=SourceSpan(57, 1)),
                MirInstruction(2, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert values[1] == len(actual.encode("utf-8"))
    assert actual == expected


def test_merit_materializes_ordered_sourced_call_arguments(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_CALL_ARGUMENT_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-call-argument-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "call", result=0, operands=(0,), symbol="compute", span=SourceSpan(57, 1)),
                MirInstruction(2, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert values[1] == len(actual.encode("utf-8"))
    assert actual == expected


def test_merit_materializes_sourced_composite_instruction_catalog(tmp_path: Path) -> None:
    cases = (
        ("enum-construct", SOURCED_ENUM_CONSTRUCT_CFG_MIR_PROBE, MirInstruction(1, "construct", result=0, symbol="variant_2", span=SourceSpan(57, 1), ownership="value")),
        ("enum-tag", SOURCED_ENUM_TAG_CFG_MIR_PROBE, MirInstruction(1, "load_field", result=0, operands=(0,), symbol="tag", span=SourceSpan(57, 1))),
        ("enum-payload", SOURCED_ENUM_PAYLOAD_CFG_MIR_PROBE, MirInstruction(1, "load_field", result=0, operands=(0,), symbol="payload_2", span=SourceSpan(57, 1))),
        ("struct-construct", SOURCED_STRUCT_CONSTRUCT_CFG_MIR_PROBE, MirInstruction(1, "construct", result=0, operands=(0,), symbol="field_2", span=SourceSpan(57, 1), ownership="owned")),
        ("struct-load", SOURCED_STRUCT_LOAD_CFG_MIR_PROBE, MirInstruction(1, "load_field", result=0, operands=(0,), symbol="field_2", span=SourceSpan(57, 1))),
        ("struct-store", SOURCED_STRUCT_STORE_CFG_MIR_PROBE, MirInstruction(1, "store_field", result=0, operands=(0,), symbol="field_2", span=SourceSpan(57, 1), ownership="owned")),
        ("struct-replace", SOURCED_STRUCT_REPLACE_CFG_MIR_PROBE, MirInstruction(1, "store_field", result=0, operands=(0,), symbol="field_2", span=SourceSpan(57, 1), ownership="moved")),
    )
    for name, probe, body_instruction in cases:
        root = _project(tmp_path / name, probe)
        project = load_project(root / "Merit.toml")
        interpreted = interpret(project)
        _, _, executable = build(project, root / "build" / name)
        native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
        assert native == interpreted
        values = [int(value) for value in native.splitlines()]
        assert values[0] == 0
        actual = bytes(values[2:]).decode("utf-8")
        expected = canonical_mir_json(MirModule("demo", (MirFunction(
            "compute", MirType("unit"), (
                MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
            ), (
                MirBlock(0, (
                    MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                    body_instruction,
                    MirInstruction(2, "drop", operands=(0,), ownership="owned"),
                ), MirTerminator("return")),
            ), 0,
        ),)))
        assert actual == expected


def test_merit_materializes_multiple_sourced_body_instructions(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_TWO_BODY_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-two-body-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value"),
                MirInstruction(2, "print", operands=(0,), span=SourceSpan(57, 1)),
                MirInstruction(3, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert actual == expected


def test_merit_materializes_multiple_sourced_locals(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_MULTIPLE_LOCALS_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-multiple-locals-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
            MirLocal(1, "_t1", MirType("i64")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value"),
                MirInstruction(2, "print", operands=(0,), span=SourceSpan(57, 1)),
                MirInstruction(3, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert actual == expected


def test_merit_materializes_sourced_callable_parameters(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_PARAMETER_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-parameter-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("Buffer"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="borrowed", source_binding_id=7),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value"),
                MirInstruction(2, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0, parameters=(MirParameter(0, "borrowed"),), return_mode="borrowed", borrowed_origin=0, exported=True,
    ),)))
    assert actual == expected


def test_merit_materializes_sourced_contract_locals(tmp_path: Path) -> None:
    root = _project(tmp_path, SOURCED_CONTRACT_LOCAL_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "sourced-contract-local-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "compute", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
            MirLocal(1, "_contract_1_10", MirType("i64")),
        ), (
            MirBlock(0, (
                MirInstruction(0, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value", contract_kind="precondition"),
                MirInstruction(1, "const", result=0, value="1", span=SourceSpan(57, 1), ownership="value"),
                MirInstruction(2, "drop", operands=(0,), ownership="owned"),
            ), MirTerminator("return")),
        ), 0,
    ),)))
    assert actual == expected


def test_sourced_cfg_rejects_mismatched_source_binding_identity(tmp_path: Path) -> None:
    root = _project(tmp_path, INVALID_SOURCED_OWNERSHIP_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "invalid-sourced-ownership-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] != 0


def test_sourced_cfg_rejects_mismatched_contract_provenance(tmp_path: Path) -> None:
    root = _project(tmp_path, INVALID_SOURCED_CONTRACT_CFG_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "invalid-sourced-contract-cfg-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] != 0


def test_merit_materializes_complete_contract_instruction_catalog(tmp_path: Path) -> None:
    root = _project(tmp_path, CONTRACT_INSTRUCTION_CATALOG_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "contract-instruction-catalog")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    expected = (
        MirInstruction(0, "const", result=0, value="1", span=SourceSpan(0, 1), ownership="value", contract_kind="precondition"),
        MirInstruction(1, "binary", result=0, operands=(0, 0), symbol="+", span=SourceSpan(0, 1), numeric_policy="exact"),
        MirInstruction(2, "contract_check", operands=(0,), span=SourceSpan(0, 1), contract_kind="postcondition"),
        MirInstruction(3, "call", result=0, operands=(0,), symbol="slice_len", span=SourceSpan(0, 1)),
        MirInstruction(4, "copy", result=0, operands=(0,), span=SourceSpan(0, 1)),
        MirInstruction(5, "load_field", result=0, operands=(0,), symbol="field_2", span=SourceSpan(0, 1)),
        MirInstruction(6, "copy", result=0, operands=(0,), span=SourceSpan(0, 1)),
    )
    values = [int(value) for value in native.splitlines()]
    cursor = 0
    for instruction in expected:
        assert values[cursor] == 0
        length = values[cursor + 1]
        actual = bytes(values[cursor + 2:cursor + 2 + length]).decode("utf-8")
        assert actual == json.dumps(instruction.to_data(), sort_keys=True, separators=(",", ":"))
        cursor += 2 + length
        assert values[cursor] == 0
        cursor += 1
    assert cursor == len(values)


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


def test_merit_materializes_required_capability_names(tmp_path: Path) -> None:
    root = _project(tmp_path, CAPABILITY_JSON_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "capability-json")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    length = values[1]
    actual = bytes(values[2:2 + length]).decode("utf-8")
    assert actual == json.dumps(["allocate", "io"], separators=(",", ":"))
    assert values[2 + length] == 2


def test_merit_materializes_callable_ownership_metadata(tmp_path: Path) -> None:
    root = _project(tmp_path, CALLABLE_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "callable-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "identity", MirType("i64"),
        (MirLocal(0, "value", MirType("i64"), ownership="borrowed", source_binding_id=7),),
        (MirBlock(0, (), MirTerminator("return", operands=(0,), span=SourceSpan(0, 1))),),
        0, parameters=(MirParameter(0, "borrowed"),), return_mode="borrowed",
        borrowed_origin=0, exported=True,
    ),)))
    assert actual == expected


def test_merit_materializes_call_and_ordered_arguments(tmp_path: Path) -> None:
    root = _project(tmp_path, CALL_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "call-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "caller", MirType("i64"), (
            MirLocal(0, "arg", MirType("i64"), source_binding_id=7),
            MirLocal(1, "_t0", MirType("i64")),
        ), (MirBlock(0, (
            MirInstruction(0, "call", result=1, operands=(0,), symbol="callee", span=SourceSpan(7, 6)),
        ), MirTerminator("return", operands=(1,), span=SourceSpan(0, 1))),), 0,
        parameters=(MirParameter(0, "value"),),
    ),)))
    assert actual == expected


def test_merit_preserves_borrowed_temporary_mode(tmp_path: Path) -> None:
    root = _project(tmp_path, BORROWED_TEMP_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "borrowed-temp-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    actual = bytes(values[2:]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "identity", MirType("i64"), (
            MirLocal(0, "value", MirType("i64"), ownership="borrowed", source_binding_id=7),
            MirLocal(1, "_t0", MirType("i64"), ownership="borrowed"),
        ), (MirBlock(0, (), MirTerminator("return", operands=(1,), span=SourceSpan(0, 1))),), 0,
        parameters=(MirParameter(0, "borrowed"),), return_mode="borrowed", borrowed_origin=0,
    ),)))
    assert actual == expected


def test_merit_materializes_owned_source_local_from_binding(tmp_path: Path) -> None:
    root = _project(tmp_path, OWNED_SOURCE_LOCAL_MIR_PROBE)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "owned-source-local-mir")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(value) for value in native.splitlines()]
    assert values[0] == 0
    length = values[1]
    actual = bytes(values[2:2 + length]).decode("utf-8")
    expected = canonical_mir_json(MirModule("demo", (MirFunction(
        "owned", MirType("unit"), (
            MirLocal(0, "item", MirType("Buffer"), mutable=True, ownership="owned", source_binding_id=7),
        ), (MirBlock(0, (), MirTerminator("return", span=SourceSpan(0, 1))),), 0,
    ),)))
    assert actual == expected
    assert values[2 + length] == 8
