"""Native RM1 source-body records retain the origin without an owner copy."""

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


def test_native_local_borrow_create_record_matches_interpreter(tmp_path: Path) -> None:
    root = tmp_path / "local_borrow_records"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build", ".merit"))
    lexer = root / "src/lexer.mrt"
    replaced, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {",
                              lexer.read_text(encoding="utf-8"), count=1)
    assert count == 1
    lexer.write_text(replaced, encoding="utf-8")
    (root / "src/local_borrow_records_probe.mrt").write_text('''module local_borrow_records_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_semantics;
import bootstrap_mir_functions;
import bootstrap_mir_source_function_records;
import bootstrap_mir_source_function_record_stats;
import bootstrap_mir_structured_lowering;
capability allocate;
fn main()->i32 { with capability allocate {
 let allocator:Allocator=system_allocator();
 let source:Buffer=buffer_from_string(allocator,"module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(r); return 0; }");
 let tokens:Vec<Token>=lex(source,allocator);
 let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
 let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
 var enums:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,0);
 var structs:Vec<I64StructCatalogEntry>=vec_new<I64StructCatalogEntry>(allocator,0);
 var arms:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(allocator,0);
 var records:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,12);
 var events:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,12);
 print(lower_source_function_body_records(source,tokens,statements,operands,enums,structs,arms,allocator,records,events));
 var stats:Vec<i64>=vec_new<i64>(allocator,4);
 print(source_function_record_stats(records,stats));
 print(validate_function_mir_cfg_records(records)==function_mir_unknown_record_kind_status());
 print(validate_function_mir_local_borrow_cfg_records(records));
 var index:i64=0;
 while(index<vec_len<MirFunctionRecord>(records)){
  let record:MirFunctionRecord=vec_get<MirFunctionRecord>(records,index);
  if(function_mir_kind(record)==function_mir_kind_local_reference()){
   print(function_mir_binding_id(record));print(function_mir_type_code(record));
  }
  if(function_mir_kind(record)==function_mir_kind_local_borrow_create()){
   print(function_mir_result(record));print(function_mir_left(record));
  }
  index=checked_add(index,1);
 }
 drop(stats);drop(events);drop(records);drop(arms);drop(structs);drop(enums);
 drop(operands);drop(statements);drop(tokens);drop(source);
 } return 0; }
''', encoding="utf-8", newline="\n")
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        'entry = "src/lexer.mrt"', 'entry = "src/local_borrow_records_probe.mrt"'
    ), encoding="utf-8")
    project = load_project(manifest)
    expected = "0\n0\n1\n0\n1\n7\n1\n0\n"
    assert interpret(project) == expected
    _, _, executable = build(project, root / "native")
    assert subprocess.run([str(executable)], check=True, text=True,
                          capture_output=True).stdout == expected
