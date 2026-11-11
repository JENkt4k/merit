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
import bootstrap_mir_source_type_lifecycle;
import bootstrap_mir_source_ownership_metadata;
import bootstrap_mir_ownership_flow;
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
    var uses:Vec<SourceLocalLoanUse>=vec_new<SourceLocalLoanUse>(allocator,4);
    if(status==0){
        print(derive_source_local_loan_uses(source,tokens,statements,operands,parameters,0,parameter_count,loans,allocator,uses));
        print(vec_len<SourceLocalLoanUse>(uses));
        index=0;
        while(index<vec_len<SourceLocalLoanUse>(uses)){
            let use:SourceLocalLoanUse=vec_get<SourceLocalLoanUse>(uses,index);
            print(source_local_loan_use_reference(use));print(source_local_loan_use_statement(use));
            index=checked_add(index,1);
        }
        var ends:Vec<SourceLocalLoanEnd>=vec_new<SourceLocalLoanEnd>(allocator,2);
        print(derive_source_local_loan_ends(loans,uses,ends));
        print(vec_len<SourceLocalLoanEnd>(ends));
        index=0;
        while(index<vec_len<SourceLocalLoanEnd>(ends)){
            let end:SourceLocalLoanEnd=vec_get<SourceLocalLoanEnd>(ends,index);
            print(source_local_loan_end_reference(end));print(source_local_loan_end_statement(end));
            index=checked_add(index,1);
        }
        drop(ends);
    }
    drop(uses);
    drop(loans);drop(parameters);drop(operands);drop(statements);drop(tokens);drop(source);
    return 0;
}
fn check_cleanup_authority()->i32 requires_caps [allocate] {
    let allocator:Allocator=system_allocator();
    let source:Buffer=buffer_from_string(allocator,
        "module m\\nstruct Box { value:i32; } destructor Box { print(9); } fn main()->i32 { let x:Box=Box{value:1}; let r: borrow Box=borrow x; print(r.value); return 0; }");
    let tokens:Vec<Token>=lex(source,allocator);
    let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
    let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
    var types:Vec<SourceTypeOwnershipEntry>=vec_new<SourceTypeOwnershipEntry>(allocator,2);
    var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,2);
    print(derive_source_type_ownership_catalog(source,tokens,statements,operands,types));
    print(derive_source_ownership_bindings(source,statements,operands,types,bindings));
    print(vec_len<MirOwnershipBinding>(bindings));
    var index:i64=0;
    while(index<vec_len<MirOwnershipBinding>(bindings)){
        let binding:MirOwnershipBinding=vec_get<MirOwnershipBinding>(bindings,index);
        print(ownership_binding_owned(binding));
        index=checked_add(index,1);
    }
    drop(bindings);drop(types);drop(operands);drop(statements);drop(tokens);drop(source);
    return 0;
}
fn check_malformed_end_records()->i32 requires_caps [allocate] {
    let allocator:Allocator=system_allocator();
    var origins:Vec<SourceLocalLoanOrigin>=vec_new<SourceLocalLoanOrigin>(allocator,1);
    var uses:Vec<SourceLocalLoanUse>=vec_new<SourceLocalLoanUse>(allocator,1);
    var ends:Vec<SourceLocalLoanEnd>=vec_new<SourceLocalLoanEnd>(allocator,1);
    vec_push<SourceLocalLoanOrigin>(origins,SourceLocalLoanOrigin{
        reference_binding_id:1,origin_binding_id:0,reference_start:10,origin_start:3,declaration_statement:0
    });
    vec_push<SourceLocalLoanUse>(uses,SourceLocalLoanUse{
        reference_binding_id:1,statement_index:0,source_start:20
    });
    print(derive_source_local_loan_ends(origins,uses,ends));
    print(vec_len<SourceLocalLoanEnd>(ends));
    vec_set<SourceLocalLoanUse>(uses,0,SourceLocalLoanUse{
        reference_binding_id:2,statement_index:1,source_start:20
    });
    print(derive_source_local_loan_ends(origins,uses,ends));
    print(vec_len<SourceLocalLoanEnd>(ends));
    drop(ends);drop(uses);drop(origins);
    return 0;
}
fn check_explicit_owner_effects(source_text:String)->i32 requires_caps [allocate] {
    let allocator:Allocator=system_allocator();
    let source:Buffer=buffer_from_string(allocator,source_text);
    let tokens:Vec<Token>=lex(source,allocator);
    let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
    let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
    var parameters:Vec<SourceFunctionParameter>=vec_new<SourceFunctionParameter>(allocator,0);
    var types:Vec<SourceTypeOwnershipEntry>=vec_new<SourceTypeOwnershipEntry>(allocator,2);
    var ownership:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,2);
    var origins:Vec<SourceLocalLoanOrigin>=vec_new<SourceLocalLoanOrigin>(allocator,2);
    var uses:Vec<SourceLocalLoanUse>=vec_new<SourceLocalLoanUse>(allocator,2);
    var ends:Vec<SourceLocalLoanEnd>=vec_new<SourceLocalLoanEnd>(allocator,2);
    let type_status:i32=derive_source_type_ownership_catalog(source,tokens,statements,operands,types);
    let binding_status:i32=derive_source_ownership_bindings(source,statements,operands,types,ownership);
    let origin_status:i32=derive_source_local_loan_origins(source,tokens,statements,operands,parameters,0,0,allocator,origins);
    let use_status:i32=derive_source_local_loan_uses(source,tokens,statements,operands,parameters,0,0,origins,allocator,uses);
    let end_status:i32=derive_source_local_loan_ends(origins,uses,ends);
    print(type_status);print(binding_status);print(origin_status);print(use_status);print(end_status);
    print(check_source_local_loan_explicit_owner_effects(
        source,tokens,statements,operands,parameters,0,0,ownership,origins,ends,allocator
    ));
    drop(ends);drop(uses);drop(origins);drop(ownership);drop(types);
    drop(parameters);drop(operands);drop(statements);drop(tokens);drop(source);
    return 0;
}
fn check_reference_use(source_text:String,signature_start:i64,signature_length:i64,parameter_mode:i32,return_mode:i32)->i32 requires_caps [allocate] {
    let allocator:Allocator=system_allocator();
    let source:Buffer=buffer_from_string(allocator,source_text);
    let tokens:Vec<Token>=lex(source,allocator);
    let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
    let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
    var parameters:Vec<SourceFunctionParameter>=vec_new<SourceFunctionParameter>(allocator,1);
    var signatures:Vec<SourceFunctionSignature>=vec_new<SourceFunctionSignature>(allocator,1);
    if(signature_start>=0){
        vec_push<SourceFunctionParameter>(parameters,SourceFunctionParameter{
            name_start:signature_start,name_length:signature_length,type_code:1,mode:parameter_mode,mutable:0
        });
        vec_push<SourceFunctionSignature>(signatures,SourceFunctionSignature{
            name_start:signature_start,name_length:signature_length,return_type_code:1,
            return_mode:return_mode,borrowed_origin:-1,parameter_start:0,parameter_count:1
        });
    }
    var origins:Vec<SourceLocalLoanOrigin>=vec_new<SourceLocalLoanOrigin>(allocator,1);
    var uses:Vec<SourceLocalLoanUse>=vec_new<SourceLocalLoanUse>(allocator,1);
    var ends:Vec<SourceLocalLoanEnd>=vec_new<SourceLocalLoanEnd>(allocator,1);
    print(derive_source_local_loan_origins(source,tokens,statements,operands,parameters,0,0,allocator,origins));
    print(derive_source_local_loan_uses(source,tokens,statements,operands,parameters,0,0,origins,allocator,uses));
    print(derive_source_local_loan_ends(origins,uses,ends));
    print(check_source_local_loan_reference_uses(source,tokens,statements,operands,origins,uses,ends,signatures,parameters));
    drop(ends);drop(uses);drop(origins);drop(signatures);drop(parameters);
    drop(operands);drop(statements);drop(tokens);drop(source);
    return 0;
}
fn check_complete_proof(source_text:String)->i32 requires_caps [allocate] {
    let allocator:Allocator=system_allocator();
    let source:Buffer=buffer_from_string(allocator,source_text);
    let tokens:Vec<Token>=lex(source,allocator);
    let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
    let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);
    var parameters:Vec<SourceFunctionParameter>=vec_new<SourceFunctionParameter>(allocator,0);
    var signatures:Vec<SourceFunctionSignature>=vec_new<SourceFunctionSignature>(allocator,0);
    var types:Vec<SourceTypeOwnershipEntry>=vec_new<SourceTypeOwnershipEntry>(allocator,2);
    var ownership:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,2);
    var origins:Vec<SourceLocalLoanOrigin>=vec_new<SourceLocalLoanOrigin>(allocator,2);
    var uses:Vec<SourceLocalLoanUse>=vec_new<SourceLocalLoanUse>(allocator,2);
    var ends:Vec<SourceLocalLoanEnd>=vec_new<SourceLocalLoanEnd>(allocator,2);
    let type_status:i32=derive_source_type_ownership_catalog(source,tokens,statements,operands,types);
    let binding_status:i32=derive_source_ownership_bindings(source,statements,operands,types,ownership);
    if(type_status!=0){return type_status;}
    if(binding_status!=0){return binding_status;}
    let proof:SourceLocalLoanProof=prove_source_local_loans(
        source,tokens,statements,operands,parameters,0,0,signatures,ownership,allocator,origins,uses,ends
    );
    print(source_local_loan_proof_stage(proof));print(source_local_loan_proof_detail(proof));
    drop(ends);drop(uses);drop(origins);drop(ownership);drop(types);
    drop(signatures);drop(parameters);drop(operands);drop(statements);drop(tokens);drop(source);
    return 0;
}
fn main()->i32 { with capability allocate {
    check_case("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(r); return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let x:i32=1; let a: borrow i32=borrow x; let b: borrow i32=borrow x; print(a); print(b); return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let r: borrow i32=borrow missing; return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; let s: borrow i32=borrow r; return 0; }",-1);
    check_case("module m\\nfn main()->i32 { let x:i32=1; var r: borrow i32=borrow x; return 0; }",-1);
    check_case("module m\\nfn inspect(borrow x:i32)->i32 { let r: borrow i32=borrow x; print(r); return 0; }",27);
    check_cleanup_authority();
    check_malformed_end_records();
    check_explicit_owner_effects("module m\\nfn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; print(r); x=2; return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; x=2; print(r); return 0; }");
    check_explicit_owner_effects("module m\\nstruct Box { value:i32; } destructor Box { print(9); } fn main()->i32 { let x:Box=Box{value:1}; let r: borrow Box=borrow x; print(r.value); let y:Box=x; return 0; }");
    check_explicit_owner_effects("module m\\nstruct Box { value:i32; } destructor Box { print(9); } fn main()->i32 { let x:Box=Box{value:1}; let r: borrow Box=borrow x; let y:Box=x; print(r.value); return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { let x:String=\\\"a\\\"; let r: borrow String=borrow x; print(r); drop(x); return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { let x:String=\\\"a\\\"; let r: borrow String=borrow x; drop(x); print(r); return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { var x:i32=1; let a: borrow i32=borrow x; let b: borrow i32=borrow x; print(a); x=2; print(b); return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; x=2; return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { let x:String=\\\"a\\\"; let r: borrow String=borrow x; replace(x,\\\"b\\\"); print(r); return 0; }");
    check_explicit_owner_effects("module m\\nfn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; let y:i32=x; print(r); return 0; }");
    check_explicit_owner_effects("module m\\ncapability io; fn main()->i32 { var x:i32=1; with capability io { let r: borrow i32=borrow x; print(r); } x=2; return 0; }");
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r); return 0; }",67,7,1,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r); return 0; }",67,7,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; inspect(r); print(r); return 0; }",67,7,1,1);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; consume(r); print(r); return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; return r; }",-1,0,0,0);
    check_reference_use("module m\\nstruct Holder { value:i32; } fn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; let h:Holder=Holder{value:r}; return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; drop(r); return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; if 1 { print(r); } return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; mutate(x); print(r); return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(mutate(x)); print(r); return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(r); mutate(x); return 0; }",-1,0,0,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; inspect(x); print(r); return 0; }",67,7,1,0);
    check_reference_use("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; mutate(x); print(r); return 0; }",67,6,2,0);
    check_complete_proof("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; print(r); return 0; }");
    check_complete_proof("module m\\nfn main()->i32 { var x:i32=1; let r: borrow i32=borrow x; x=2; print(r); return 0; }");
    check_complete_proof("module m\\nfn main()->i32 { let x:i32=1; let r: borrow i32=borrow x; mystery(r); print(r); return 0; }");
} return 0; }
'''
    (root / "src/local_loan_origin_probe.mrt").write_text(probe, encoding="utf-8")
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('entry = "src/lexer.mrt"', 'entry = "src/local_loan_origin_probe.mrt"'), encoding="utf-8")
    project = load_project(manifest)
    expected = (
        "0\n1\n1\n0\n0\n1\n1\n2\n0\n1\n1\n2\n"
        "0\n2\n1\n0\n2\n0\n0\n2\n1\n3\n2\n4\n0\n2\n1\n3\n2\n4\n"
        "3\n0\n4\n1\n1\n0\n5\n0\n"
        "0\n1\n1\n0\n0\n1\n1\n1\n0\n1\n1\n1\n"
        "0\n0\n2\n1\n0\n1\n0\n1\n0\n"
        + "".join("0\n0\n0\n0\n0\n" + f"{result}\n" for result in (0, 2, 0, 2, 0, 2, 2, 0, 2, 0, 0))
        + "".join(f"0\n0\n0\n{result}\n" for result in (0, 4, 4, 4, 3, 3, 2, 2, 4, 4, 0, 0, 4))
        + "0\n0\n4\n2\n5\n4\n"
    )
    assert interpret(project) == expected
    _, _, executable = build(project, root / "native")
    assert subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout == expected
