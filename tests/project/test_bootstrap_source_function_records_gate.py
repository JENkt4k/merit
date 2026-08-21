from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.bootstrap.mir_function_assembly_parity import lower_native_whole_function_assembly
from merit.bootstrap.mir_to_c import emit_c_module
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"
SOURCE = "module demo\nfn compute()->i64 { let x:i64=1+2; if x>2 { return x+4; } return 9; }\n"


def _probe_source() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'''module bootstrap_source_function_records_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_semantics;
import bootstrap_mir_functions;
import bootstrap_mir_source_function_records;
import bootstrap_mir_source_function_record_stats;
import bootstrap_mir_function_contracts;
import bootstrap_mir_function_instruction_source;
import bootstrap_mir_function_assembly;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_cfg;
import bootstrap_mir_cfg_placement;

capability allocate;

fn print_body(borrow value: MirFunctionRecord) -> i32 {{
 print(function_mir_kind(value)); print(function_mir_start(value)); print(function_mir_length(value));
 print(function_mir_id(value)); print(function_mir_result(value)); print(function_mir_left(value)); print(function_mir_right(value));
 print(function_mir_symbol_start(value)); print(function_mir_symbol_length(value)); print(function_mir_symbol_code(value));
 print(function_mir_type_code(value)); print(function_mir_numeric_policy(value)); print(function_mir_binding_id(value));
 print(function_mir_mutable(value)); print(function_mir_hir_node_id(value)); print(function_mir_ordinal(value)); return 0;
}}
fn print_source(borrow value: MirFunctionInstructionSource) -> i32 {{
 print(assembly_source_global_id(value)); print(assembly_source_kind(value)); print(assembly_source_id(value));
 print(assembly_source_contract_kind(value)); print(assembly_source_clause(value)); print(assembly_source_result(value));
 print(assembly_source_left(value)); print(assembly_source_right(value)); return 0;
}}
fn print_cfg(borrow value: MirCfgRecord) -> i32 {{
 print(cfg_kind(value)); print(cfg_block_id(value)); print(cfg_operand(value)); print(cfg_target_a(value));
 print(cfg_target_b(value)); print(cfg_case_value(value)); print(cfg_ordinal(value)); return 0;
}}
fn print_placement(borrow value: MirPlacementRecord) -> i32 {{
 print(placement_block_id(value)); print(placement_instruction_id(value)); print(placement_ordinal(value)); return 0;
}}

fn main() -> i32 {{
 with capability allocate {{
  let allocator:Allocator=system_allocator();
  let source:Buffer=buffer_from_string(allocator,"{escaped}");
  let tokens:Vec<Token>=lex(source,allocator);
  let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
  let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
  var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,48);
  var body_events:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,48);
  var enum_catalog:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,0);
  var struct_catalog:Vec<I64StructCatalogEntry>=vec_new<I64StructCatalogEntry>(allocator,0);
  var resolved_arms:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(allocator,0);
  print(-201); print(lower_source_function_body_records(source,tokens,statements,operands,enum_catalog,struct_catalog,resolved_arms,allocator,body,body_events));
  var stats:Vec<i64>=vec_new<i64>(allocator,4);
  print(source_function_record_stats(body,stats));
  print(vec_len<i64>(stats)); var si:i64=0; while(si<vec_len<i64>(stats)){{ print(vec_get<i64>(stats,si)); si=checked_add(si,1); }}
  print(vec_len<MirFunctionRecord>(body)); var bi:i64=0; while(bi<vec_len<MirFunctionRecord>(body)){{ let r:MirFunctionRecord=vec_get<MirFunctionRecord>(body,bi); print_body(r); bi=checked_add(bi,1); }}

  var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,0);
  var assembled:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,64);
  var sources:Vec<MirFunctionInstructionSource>=vec_new<MirFunctionInstructionSource>(allocator,64);
  print(-202); print(assemble_function_mir_events(contracts,body_events,vec_get<i64>(stats,0),vec_get<i64>(stats,1),allocator,assembled,sources));
  print(validate_function_assembly_sources(sources)); print(vec_len<MirFunctionInstructionSource>(sources));
  var ii:i64=0; while(ii<vec_len<MirFunctionInstructionSource>(sources)){{ let s:MirFunctionInstructionSource=vec_get<MirFunctionInstructionSource>(sources,ii); print_source(s); ii=checked_add(ii,1); }}

  var cfg:Vec<MirCfgRecord>=vec_new<MirCfgRecord>(allocator,32);
  var placements:Vec<MirPlacementRecord>=vec_new<MirPlacementRecord>(allocator,64);
  print(-203); print(lower_structured_mir(assembled,allocator,cfg,placements)); print(vec_len<MirCfgRecord>(cfg));
  var ci:i64=0; while(ci<vec_len<MirCfgRecord>(cfg)){{ let c:MirCfgRecord=vec_get<MirCfgRecord>(cfg,ci); print_cfg(c); ci=checked_add(ci,1); }}
  print(vec_len<MirPlacementRecord>(placements)); var pi:i64=0; while(pi<vec_len<MirPlacementRecord>(placements)){{ let p:MirPlacementRecord=vec_get<MirPlacementRecord>(placements,pi); print_placement(p); pi=checked_add(pi,1); }}
  drop(placements);drop(cfg);drop(sources);drop(assembled);drop(contracts);drop(stats);drop(body_events);drop(body);drop(operands);drop(statements);drop(tokens);drop(source);
 }}
 return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "source_function_records"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1)
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "source_function_records_probe.mrt").write_text(_probe_source(), encoding="utf-8")
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('entry = "src/lexer.mrt"', 'entry = "src/source_function_records_probe.mrt"'), encoding="utf-8")
    return load_project(manifest), root


def _rows(values: list[int], cursor: int, count: int, width: int):
    rows = []
    for _ in range(count):
        rows.append(tuple(values[cursor:cursor + width])); cursor += width
    return rows, cursor


def _parse(output: str):
    first, remainder = output.rsplit("-201\n", 1)[1].split("-202\n", 1)
    second, third = remainder.split("-203\n", 1)
    values = [int(v) for v in first.splitlines()]
    assert values[0:3] == [0, 0, 4]
    stats = tuple(values[3:7]); cursor = 7
    body_count = values[cursor]; cursor += 1
    body, cursor = _rows(values, cursor, body_count, 16); assert cursor == len(values)
    values = [int(v) for v in second.splitlines()]
    assert values[0:2] == [0, 0]
    source_count = values[2]; sources, cursor = _rows(values, 3, source_count, 8); assert cursor == len(values)
    values = [int(v) for v in third.splitlines()]
    assert values[0] == 0
    cfg_count = values[1]; cfg, cursor = _rows(values, 2, cfg_count, 7)
    placement_count = values[cursor]; cursor += 1
    placements, cursor = _rows(values, cursor, placement_count, 3); assert cursor == len(values)
    return stats, body, sources, cfg, placements


def test_real_source_body_reaches_canonical_cfg_and_deterministic_c(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _parse(interpret(project))
    _, _, executable = build(project, root / "native")
    native = _parse(subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout)
    assert native == interpreted
    stats, body, sources, cfg, placements = interpreted
    assert stats[0] == 1 and stats[1] > stats[0] and stats[2] == len(sources) and stats[3] == 2
    module = lower_native_whole_function_assembly(
        source=SOURCE, module_name="demo", body_records=body, contract_records=(), contract_locals=(),
        instruction_sources=sources, cfg_records=cfg, placements=placements,
        capability_ids=(), capability_names={},
    )
    function = module.functions[0]
    assert function.name == "compute"
    assert len(function.blocks) >= 3
    assert sum(block.terminator.kind == "return" for block in function.blocks) == 2
    assert any(block.terminator.kind == "branch" for block in function.blocks)
    c_source = emit_c_module(module) + '\n#include <stdio.h>\nint main(void){printf("%lld\\n",(long long)compute());return 0;}\n'
    c_path = root / "replacement.c"; c_path.write_text(c_source, encoding="utf-8")
    replacement = root / "replacement"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-O2", str(c_path), "-o", str(replacement)], check=True, text=True, capture_output=True)
    assert subprocess.run([str(replacement)], check=True, text=True, capture_output=True).stdout.strip() == "7"
