from pathlib import Path
import re
import shutil
import subprocess

import pytest

from merit.bootstrap.mir_to_c import emit_c_module
from merit.bootstrap.resolved_source_function_snapshot import (
    decode_resolved_source_function_snapshot,
    materialize_resolved_source_function_snapshot,
)
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
SOURCE = (
    "module demo\n"
    "enum Choice { Left(i64), Right(i64), Other(i64) }\n"
    "capability clock;\n"
    "fn compute()->i64\n"
    "requires_caps [clock]\n"
    "requires 1 < 2;\n"
    "ensures 2 > 1;\n"
    "{ let a:Resource=1; let flag:Choice=Right(1); match flag { Left(x) => { drop(a); return 1; } "
    "Right(y) => { drop(a); } Other(z) => { drop(a); } } with capability clock { return 2; } }\n"
)


def _probe() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    left, right, other, clock = (SOURCE.index(x) for x in ("Left", "Right", "Other", "clock"))
    return f'''module real_source_function_assembly_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_semantics;
import bootstrap_mir_functions;
import bootstrap_mir_function_clause_metadata;
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_assembly_plan;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_match_capability_flow;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;
import bootstrap_mir_resolved_source_function_assembly;
import bootstrap_mir_resolved_source_function_snapshot;

capability allocate;

fn main()->i32 {{
 with capability allocate {{
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"{escaped}");
  let tokens:Vec<Token>=lex(source,allocator);
  let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
  let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
  var variants:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,3);
  vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:7,enum_name_start:0,enum_name_length:0,variant_id:70,ordinal:0,name_start:{left},name_length:4,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
  vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:7,enum_name_start:0,enum_name_length:0,variant_id:71,ordinal:1,name_start:{right},name_length:5,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
  vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:7,enum_name_start:0,enum_name_length:0,variant_id:72,ordinal:2,name_start:{other},name_length:5,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
  var capabilities:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,1);
  vec_push<CapabilityCatalogEntry>(capabilities,CapabilityCatalogEntry{{capability_id:9,name_start:{clock},name_length:5}});
  var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,2);
  vec_push<MirOwnershipBinding>(bindings,ownership_binding(0,0,1,0));
  vec_push<MirOwnershipBinding>(bindings,ownership_binding(1,1,0,0));

  var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,96);
  var metadata:Vec<MirFunctionClauseMetadata>=vec_new<MirFunctionClauseMetadata>(allocator,8);
  var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,32);
  var arms:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(allocator,4);
  var scopes:Vec<ResolvedCapabilityScope>=vec_new<ResolvedCapabilityScope>(allocator,2);
  var ownership_events:Vec<MirOwnershipEvent>=vec_new<MirOwnershipEvent>(allocator,96);
  var effects:Vec<MirCapabilityEffect>=vec_new<MirCapabilityEffect>(allocator,4);
  var ownership_records:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,64);
  var contract_locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,16);
  var required:Vec<i64>=vec_new<i64>(allocator,4);
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,128);
  var assembled:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,160);
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,64);
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,128);
  var structs:Vec<I64StructCatalogEntry>=vec_new<I64StructCatalogEntry>(allocator,0);

  print(lower_resolved_source_function_assembly(
    source,tokens,statements,operands,variants,structs,7,capabilities,bindings,allocator,
    body,metadata,contracts,arms,scopes,ownership_events,effects,ownership_records,
    contract_locals,required,sources,assembled,cfg,placements
  ));
  print(vec_len<MirFunctionRecord>(body)); print(vec_len<ResolvedMatchArm>(arms));
  print(vec_len<ResolvedCapabilityScope>(scopes)); print(vec_len<MirCapabilityEffect>(effects));
  print(vec_len<MirFunctionContractLocal>(contract_locals)); print(vec_len<i64>(required));
  print(vec_get<i64>(required,0)); print(vec_len<MirFunctionInstructionSource>(sources));
  print(vec_len<MirPlacementRecord>(placements)); print(vec_len<MirCfgRecord>(cfg));
  var body_sources:i64=0; var ownership_sources:i64=0; var contract_sources:i64=0;
  var i:i64=0;
  while(i<vec_len<MirFunctionInstructionSource>(sources)){{
    let s:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,i);
    let kind:i32=assembly_source_kind(s);
    if(kind==1){{contract_sources=checked_add(contract_sources,1);}}
    if(kind==2){{body_sources=checked_add(body_sources,1);}}
    if(kind==3){{ownership_sources=checked_add(ownership_sources,1);}}
    i=checked_add(i,1);
  }}
  print(contract_sources); print(body_sources); print(ownership_sources);
  var switches:i64=0; var returns:i64=0; var unreachable:i64=0;
  i=0;
  while(i<vec_len<MirCfgRecord>(cfg)){{
    let row:MirCfgRecord=vec_get<MirCfgRecord>(cfg,i); let kind:i32=cfg_kind(row);
    if(kind==13){{switches=checked_add(switches,1);}}
    if(kind==15){{returns=checked_add(returns,1);}}
    if(kind==16){{unreachable=checked_add(unreachable,1);}}
    i=checked_add(i,1);
  }}
  print(switches); print(returns); print(unreachable);
  var type_descriptors:Vec<MirTypeDescriptor>=vec_new<MirTypeDescriptor>(allocator,0);
  print_resolved_source_function_snapshot(body,contracts,contract_locals,sources,bindings,ownership_records,cfg,placements,required,type_descriptors);

  drop(type_descriptors); drop(placements); drop(cfg); drop(assembled); drop(sources); drop(required); drop(contract_locals);
  drop(ownership_records); drop(effects); drop(ownership_events); drop(scopes); drop(arms);
  drop(contracts); drop(metadata); drop(body); drop(bindings); drop(capabilities); drop(variants);
  drop(operands); drop(statements); drop(tokens); drop(source);
 }}
 return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "real_source_function_assembly"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "real_source_function_assembly_probe.mrt").write_text(_probe())
    manifest = root / "Merit.toml"
    manifest_text = manifest.read_text()
    manifest_text, count = re.subn(
        r'entry\s*=\s*"src/lexer\.mrt"',
        'entry = "src/real_source_function_assembly_probe.mrt"',
        manifest_text,
        count=1,
    )
    assert count == 1
    manifest.write_text(manifest_text)
    return root


def test_real_source_function_reaches_unified_cfg_with_native_parity(tmp_path: Path):
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "real-source-function-assembly")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(line) for line in native.splitlines()]
    assert values[0] == 0
    assert values[2:4] == [3, 1]
    assert values[4] == 2
    assert values[6:8] == [1, 9]
    assert values[8] == values[9]
    assert values[10] > 0
    assert values[11] > 0
    assert values[12] > 0
    assert values[13] >= 3
    assert values[14] >= 3
    assert values[15] == 2
    assert values[16] == 1

    snapshot = decode_resolved_source_function_snapshot(values[17:])
    module = materialize_resolved_source_function_snapshot(
        source=SOURCE,
        module_name="demo",
        snapshot=snapshot,
        capability_names={9: "clock"},
    )
    function = module.functions[0]
    assert function.name == "compute"
    assert function.capabilities == ("clock",)
    assert any(block.terminator.kind == "switch" for block in function.blocks)
    assert sum(block.terminator.kind == "return" for block in function.blocks) == 2
    assert any(block.terminator.kind == "unreachable" for block in function.blocks)
    assert any(instruction.kind == "drop" for block in function.blocks for instruction in block.instructions)
    assert sum(
        instruction.contract_kind == "postcondition"
        for block in function.blocks
        for instruction in block.instructions
    ) == 2

    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler is unavailable")
    c_source = emit_c_module(module) + '\n#include <stdio.h>\nint main(void){ printf("%lld\\n", (long long)compute()); return 0; }\n'
    c_path = tmp_path / "real_source_canonical.c"
    canonical_executable = tmp_path / "real_source_canonical"
    c_path.write_text(c_source, encoding="utf-8")
    subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-O2", str(c_path), "-o", str(canonical_executable)],
        check=True,
        text=True,
        capture_output=True,
    )
    canonical = subprocess.run(
        [str(canonical_executable)], check=True, text=True, capture_output=True
    ).stdout
    assert canonical.strip() == "2"
