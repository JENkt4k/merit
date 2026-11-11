"""Native source-origin identity for RM1, before the loan checker is enabled."""

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples/projects/bootstrap_lexer"


def test_native_local_loan_origin_catalog_matches_interpreter(tmp_path):
    root = tmp_path / "local_loan_origin"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src/lexer.mrt"
    source, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(encoding="utf-8"), count=1)
    assert count == 1
    lexer.write_text(source, encoding="utf-8")
    probe = '''module local_loan_origin_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_mir_source_function_records;
capability allocate;
fn check_case(source_text:String,parameter_name_start:i64)->i32 requires_caps [allocate] {
    let allocator:Allocator=system_allocator();
    let source:Buffer=buffer_from_string(allocator,source_text);
    let tokens:Vec<Token>=lex(source,allocator);
    let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
    let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
    var parameters:Vec<SourceFunctionParameter>=vec_new<SourceFunctionParameter>(allocator,0);
    var parameter_count:i64=0;
    if(parameter_name_start>=0){
        vec_push<SourceFunctionParameter>(parameters,SourceFunctionParameter{
            name_start:parameter_name_start,name_length:1,type_code:1,mode:1,mutable:0
        });
        parameter_count=1;
    }
    var loans:Vec<SourceLocalLoanOrigin>=vec_new<SourceLocalLoanOrigin>(allocator,2);
    let status:i32=derive_source_local_loan_origins(source,tokens,statements,operands,parameters,0,parameter_count,allocator,loans);
    print(status);print(vec_len<SourceLocalLoanOrigin>(loans));
    var index:i64=0;
    while(index<vec_len<SourceLocalLoanOrigin>(loans)){
        let loan:SourceLocalLoanOrigin=vec_get<SourceLocalLoanOrigin>(loans,index);
        print(source_local_loan_reference_binding(loan));print(source_local_loan_origin_binding(loan));
        index=checked_add(index,1);
    }
    drop(loans);drop(parameters);drop(operands);drop(statements);drop(tokens);drop(source);
    return 0;
}
fn main()->i32 { with capability allocate {
    check_case("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(r); return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let x:i32=1; let a: borrow i32=borrow x; let b: borrow i32=borrow x; print(a); print(b); return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let r: borrow i32=borrow missing; return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; let s: borrow i32=borrow r; return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let x:i32=1; var r: borrow i32=borrow x; return 0; }",-1);
    check_case("module m\\nfn inspect(borrow x:i32)->i32 { let r: borrow i32=borrow x; print(r); return 0; }",27);
} return 0; }
'''
    (root / "src/local_loan_origin_probe.mrt").write_text(probe, encoding="utf-8")
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('entry = "src/lexer.mrt"', 'entry = "src/local_loan_origin_probe.mrt"'), encoding="utf-8")
    project = load_project(manifest)
    expected = "0\n1\n1\n0\n0\n2\n1\n0\n2\n0\n3\n0\n4\n1\n1\n0\n5\n0\n0\n1\n1\n0\n"
    assert interpret(project) == expected
    _, _, executable = build(project, root / "native")
    assert subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout == expected
