"""Focused canonical MIR evidence for Merit-owned destructor materialization."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from merit.bootstrap.mir_contract import canonical_mir_json, parse_mir
from merit.bootstrap.mir_to_c import _destructor_c_name, _emit_c_destructor, _type
from merit.project.build import build, interpret
from merit.project.loader import load_project


def test_native_destructor_cfg_writer_matches_canonical_mir_contract(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    root = tmp_path / "destructor-writer"
    shutil.copytree(repository / "examples/projects/bootstrap_lexer", root,
                    ignore=shutil.ignore_patterns("build", ".merit"))
    lexer = root / "src/lexer.mrt"
    renamed_source, count = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
        lexer.read_text(encoding="utf-8"), count=1,
    )
    assert count == 1
    lexer.write_text(renamed_source, encoding="utf-8", newline="\n")
    (root / "src/destructor_writer_probe.mrt").write_text(
        """module destructor_writer_probe
import bootstrap_mir_functions;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_function_contracts;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_resolved_source_function_bundle;
capability allocate;
fn main()->i32 {
 with capability allocate {
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"selfMarkerfield");
  var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,3);
  vec_push<MirFunctionRecord>(body,function_mir_header(0,4,0,4,function_mir_unit_type_code()));
  vec_push<MirFunctionRecord>(body,function_mir_source_local(
      0,4,0,function_mir_aggregate_struct_type_code(0),0,1
  ));
  vec_push<MirFunctionRecord>(body,function_mir_return(0,0,-1,0));
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,2);
  vec_push<MirCfgRecord>(cfg,cfg_block(0,0));
  vec_push<MirCfgRecord>(cfg,cfg_return_unit(0));
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,0);
  var types:Vec<MirTypeDescriptor>=vec_new<MirTypeDescriptor>(allocator,1);
  vec_push<MirTypeDescriptor>(types,function_mir_type_descriptor(
      function_mir_aggregate_struct_type_code(0),function_mir_type_descriptor_aggregate_struct_kind(),
      0,function_mir_i64_type_code(),1,0,4,6,10,5,0
  ));
  var numerics:Vec<MirNumericTypeDescriptor>=vec_new<MirNumericTypeDescriptor>(allocator,0);
  let descriptor:MirDestructorDescriptor=function_mir_destructor_descriptor(
      function_mir_aggregate_struct_type_code(0),0,3,0,2,0,0
  );
  var output:Buffer=buffer_new(allocator,1024);
  let status:i32=materialize_canonical_destructor_from_catalog(
      source,descriptor,body,cfg,placements,types,numerics,output
  );
  print(status);
  print(buffer_len(output));
  var index:i64=0;
  while(index<buffer_len(output)){print(buffer_get(output,index));index=checked_add(index,1);}
  var items:Buffer=buffer_new(allocator,1024);
  let append_status:i32=canonical_mir_append_project_destructor(output,0,allocator,items);
  print(append_status);
  var functions:Buffer=buffer_from_string(allocator,"{\\"functions\\":[{}");
  var project:Buffer=buffer_new(allocator,1024);
  let finish_status:i32=canonical_mir_finish_project_source_with_destructors(
      source,0,4,1,functions,1,items,project
  );
  print(finish_status);
  print(buffer_len(project));
  index=0;
  while(index<buffer_len(project)){print(buffer_get(project,index));index=checked_add(index,1);}
  var callable:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,0);
  var prototypes:Buffer=buffer_new(allocator,256);
  var bodies:Buffer=buffer_new(allocator,256);
  var public_header:Buffer=buffer_new(allocator,0);
  var features:Vec<i64>=vec_new<i64>(allocator,0);
  let c_status:i32=canonical_c_append_destructor_from_catalog(
      source,descriptor,body,cfg,placements,callable,types,numerics,
      prototypes,bodies,public_header,features
  );
  print(c_status);
  print(buffer_len(prototypes));
  index=0;
  while(index<buffer_len(prototypes)){print(buffer_get(prototypes,index));index=checked_add(index,1);}
  print(buffer_len(bodies));
  index=0;
  while(index<buffer_len(bodies)){print(buffer_get(bodies,index));index=checked_add(index,1);}
  drop(features);drop(public_header);drop(bodies);drop(prototypes);drop(callable);
  drop(project);drop(functions);drop(items);
  drop(output);drop(numerics);drop(types);drop(placements);drop(cfg);drop(body);drop(source);
 }
 return 0;
}
""", encoding="utf-8", newline="\n",
    )
    manifest = root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace('entry = "src/lexer.mrt"', 'entry = "src/destructor_writer_probe.mrt"'),
        encoding="utf-8", newline="\n",
    )
    project = load_project(manifest)
    interpreted = interpret(project)
    _, _, executable = build(project, tmp_path / "build" / "writer")
    native = subprocess.run([str(executable)], check=True, capture_output=True, text=True).stdout
    assert native == interpreted
    values = [int(line) for line in native.splitlines()]
    assert values.pop(0) == 0
    length = values.pop(0)
    canonical = bytes(values[:length]).decode("utf-8")
    del values[:length]
    module = parse_mir(json.loads(canonical))
    assert canonical == canonical_mir_json(module)
    assert len(module.destructors) == 1
    assert module.destructors[0].target.name.startswith("struct_aggregate_0_destructor_0")
    assert module.destructors[0].locals[0].name == "self"
    assert module.destructors[0].locals[0].ownership == "mutable_borrow"
    assert values.pop(0) == 0
    assert values.pop(0) == 0
    project_length = values.pop(0)
    assembled = bytes(values[:project_length]).decode("utf-8")
    assembled_json = json.loads(assembled)
    assert assembled_json["destructors"] == json.loads(canonical)["destructors"]
    assert assembled_json["functions"] == [{}]
    assert assembled_json["name"] == "self"
    del values[:project_length]
    assert values.pop(0) == 0
    prototype_length = values.pop(0)
    prototype = bytes(values[:prototype_length]).decode("utf-8")
    del values[:prototype_length]
    destructor = module.destructors[0]
    assert prototype == (
        f"static void {_destructor_c_name(destructor.target)}"
        f"({_type(destructor.target)} *self);\n"
    )
    body_length = values.pop(0)
    body = bytes(values[:body_length]).decode("utf-8")
    assert len(values) == body_length
    assert body == _emit_c_destructor(destructor, {}, {destructor.target: destructor})
