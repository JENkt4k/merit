from __future__ import annotations
from pathlib import Path
import re, shutil, subprocess
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'examples/projects/bootstrap_lexer'
SOURCE='module demo\nfn compute(x:i64)->i64\nrequires x > 0;\nensures x >= 0;\n{ return x; }\n'

def probe():
    escaped=SOURCE.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n'); x=SOURCE.index('x:i64')
    return f'''module function_contract_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_clauses;
import bootstrap_mir_function_contracts;
capability allocate;
fn main()->i32 {{ with capability allocate {{
 let a:Allocator=system_allocator(); let source:Buffer=buffer_from_string(a,"{escaped}"); let tokens:Vec<Token>=lex(source,a);
 let clauses:Vec<ClauseRecord>=parse_clause_records(source,tokens,a); let operands:Vec<ClauseOperand>=parse_clause_operands(source,tokens,a);
 var starts:Vec<i64>=vec_new<i64>(a,1); var lengths:Vec<i64>=vec_new<i64>(a,1); vec_push<i64>(starts,{x}); vec_push<i64>(lengths,1);
 var out:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(a,16); print(lower_function_contract_mir(source,tokens,clauses,operands,starts,lengths,a,out)); print(validate_function_contract_mir(out)); print(vec_len<MirFunctionContractRecord>(out));
 var i:i64=0; while(i<vec_len<MirFunctionContractRecord>(out)){{ let v:MirFunctionContractRecord=vec_get<MirFunctionContractRecord>(out,i); print(function_contract_kind(v)); print(function_contract_clause(v)); print(function_contract_contract_kind(v)); print(function_contract_id(v)); print(function_contract_result(v)); print(function_contract_left(v)); print(function_contract_right(v)); i=checked_add(i,1); }}
 drop(out); drop(lengths); drop(starts); drop(operands); drop(clauses); drop(tokens); drop(source); }} return 0; }}
'''

def project(tmp_path):
    root=tmp_path/'function_contract'; shutil.copytree(PROJECT,root,ignore=shutil.ignore_patterns('build'))
    p=root/'src/lexer.mrt'; text=p.read_text(); text,n=re.subn(r'\nfn main\(\) -> i32 \{','\nfn fixture_main() -> i32 {',text,count=1); assert n==1; p.write_text(text)
    (root/'src/function_contract_probe.mrt').write_text(probe()); m=root/'Merit.toml'; m.write_text(m.read_text().replace('entry = "src/lexer.mrt"','entry = "src/function_contract_probe.mrt"')); return load_project(m),root

def ints(text): return [int(x) for x in text.splitlines()]

def test_contract_spans_flow_through_ast_hir_and_mir_natively(tmp_path):
    p,root=project(tmp_path); values=ints(interpret(p)); assert values[:3]==[0,0,10]
    rows=[values[3+i*7:3+(i+1)*7] for i in range(10)]; assert 3+70==len(values)
    assert [r[0] for r in rows]==[1,1,2,3,4,1,1,2,3,4]
    assert [r[2] for r in rows]==[1,1,1,1,1,2,2,2,2,2]
    assert rows[0][3]==1 and rows[1][3]==2
    assert rows[2][3:5]==[0,2] and rows[3][3:7]==[1,1,0,2] and rows[4][3]==2 and rows[4][5]==1
    assert rows[5][3]==3 and rows[6][3]==4
    assert rows[7][3:5]==[3,4] and rows[8][3:7]==[4,3,0,4] and rows[9][3]==5 and rows[9][5]==3
    _,_,exe=build(p,root/'native'); native=subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout; assert ints(native)==values
