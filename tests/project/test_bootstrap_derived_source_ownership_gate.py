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
    "struct Resource { value:i64; }\n"
    "fn compute()->i64 { let a:Resource=1; let x:i64=2; drop(a); return x; }\n"
)


def _probe() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module derived_source_ownership_probe
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
import bootstrap_mir_source_ownership_metadata;
import bootstrap_mir_source_type_lifecycle;
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
  var variants:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,0);
  var capabilities:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,0);
  var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,2);

  var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,64);
  var metadata:Vec<MirFunctionClauseMetadata>=vec_new<MirFunctionClauseMetadata>(allocator,4);
  var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,8);
  var arms:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(allocator,0);
  var scopes:Vec<ResolvedCapabilityScope>=vec_new<ResolvedCapabilityScope>(allocator,0);
  var ownership_events:Vec<MirOwnershipEvent>=vec_new<MirOwnershipEvent>(allocator,32);
  var effects:Vec<MirCapabilityEffect>=vec_new<MirCapabilityEffect>(allocator,0);
  var ownership_records:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,16);
  var contract_locals:Vec<MirFunctionContractLocal>=vec_new<MirFunctionContractLocal>(allocator,4);
  var required:Vec<i64>=vec_new<i64>(allocator,0);
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,64);
  var assembled:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,64);
  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,16);
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,64);
  var structs:Vec<I64StructCatalogEntry>=vec_new<I64StructCatalogEntry>(allocator,0);

  print(lower_resolved_source_function_assembly_from_source(
    source,tokens,statements,operands,variants,structs,-1,capabilities,allocator,
    bindings,body,metadata,contracts,arms,scopes,ownership_events,effects,ownership_records,
    contract_locals,required,sources,assembled,cfg,placements
  ));
  print(vec_len<MirOwnershipBinding>(bindings));
  let first:MirOwnershipBinding=vec_get<MirOwnershipBinding>(bindings,0);
  let second:MirOwnershipBinding=vec_get<MirOwnershipBinding>(bindings,1);
  print(ownership_binding_id(first)); print(ownership_binding_local_id(first));
  print(ownership_binding_owned(first)); print(ownership_binding_mutable(first));
  print(ownership_binding_id(second)); print(ownership_binding_local_id(second));
  print(ownership_binding_owned(second)); print(ownership_binding_mutable(second));
  print_resolved_source_function_snapshot(body,contracts,contract_locals,sources,bindings,ownership_records,cfg,placements,required);

  drop(placements); drop(cfg); drop(assembled); drop(sources); drop(required); drop(contract_locals);
  drop(ownership_records); drop(effects); drop(ownership_events); drop(scopes); drop(arms);
  drop(contracts); drop(metadata); drop(body); drop(bindings);
  drop(capabilities); drop(variants); drop(operands); drop(statements); drop(tokens); drop(source);
 }}
 return 0;
}}
'''


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "derived_source_ownership"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "derived_source_ownership_probe.mrt").write_text(_probe())
    manifest = root / "Merit.toml"
    text = manifest.read_text()
    text, count = re.subn(
        r'entry\s*=\s*"src/lexer\.mrt"',
        'entry = "src/derived_source_ownership_probe.mrt"',
        text,
        count=1,
    )
    assert count == 1
    manifest.write_text(text)
    return root


def test_source_declared_types_drive_ownership_into_canonical_c(tmp_path: Path):
    root = _project(tmp_path)
    project = load_project(root / "Merit.toml")
    interpreted = interpret(project)
    _, _, executable = build(project, root / "build" / "derived-source-ownership")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert native == interpreted
    values = [int(line) for line in native.splitlines()]
    assert values[:10] == [0, 2, 0, 0, 1, 0, 1, 1, 0, 0]

    snapshot = decode_resolved_source_function_snapshot(values[10:])
    module = materialize_resolved_source_function_snapshot(
        source=SOURCE,
        module_name="demo",
        snapshot=snapshot,
        capability_names={},
    )
    function = module.functions[0]
    assert function.name == "compute"
    assert function.locals[0].ownership == "owned"
    assert function.locals[1].ownership != "owned"
    assert any(instruction.kind == "drop" for block in function.blocks for instruction in block.instructions)

    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("system C compiler is unavailable")
    c_source = emit_c_module(module) + '\n#include <stdio.h>\nint main(void){ printf("%lld\\n", (long long)compute()); return 0; }\n'
    c_path = tmp_path / "derived_source_ownership.c"
    canonical_executable = tmp_path / "derived_source_ownership_canonical"
    c_path.write_text(c_source, encoding="utf-8")
    compiled = subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-O2", str(c_path), "-o", str(canonical_executable)],
        text=True,
        capture_output=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    canonical = subprocess.run(
        [str(canonical_executable)], check=True, text=True, capture_output=True
    ).stdout
    assert canonical.strip() == "2"
