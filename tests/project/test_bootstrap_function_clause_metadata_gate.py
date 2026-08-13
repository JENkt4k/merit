from __future__ import annotations
from pathlib import Path
import re, shutil, subprocess
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'examples/projects/bootstrap_lexer'
SOURCE='module demo\ncapability clock;\nfn compute(x:i64)->i64\neffects [pure]\nrequires_caps [clock]\n{ return x; }\n'

def probe():
    escaped=SOURCE.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')
    clock=SOURCE.index('clock')
    return f'''module clause_metadata_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_clauses;
import bootstrap_statement_semantics;
import bootstrap_mir_function_clause_metadata;
capability allocate;
fn main()->i32 {{ with capability allocate {{
 let a:Allocator=system_allocator(); let source:Buffer=buffer_from_string(a,"{escaped}");
 let tokens:Vec<Token>=lex(source,a); let clauses:Vec<ClauseRecord>=parse_clause_records(source,tokens,a); let operands:Vec<ClauseOperand>=parse_clause_operands(source,tokens,a);
 var catalog:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(a,1); vec_push<CapabilityCatalogEntry>(catalog,CapabilityCatalogEntry{{capability_id:42,name_start:{clock},name_length:5}});
 var out:Vec<MirFunctionClauseMetadata>=vec_new<MirFunctionClauseMetadata>(a,4); print(lower_function_clause_metadata(source,clauses,operands,catalog,out)); print(validate_function_clause_metadata(out)); print(vec_len<MirFunctionClauseMetadata>(out));
 var i:i64=0; while(i<vec_len<MirFunctionClauseMetadata>(out)){{ let v:MirFunctionClauseMetadata=vec_get<MirFunctionClauseMetadata>(out,i); print(clause_metadata_kind(v)); print(clause_metadata_clause(v)); print(clause_metadata_operand(v)); print(clause_metadata_length(v)); print(clause_metadata_semantic_id(v)); i=checked_add(i,1); }}
 var empty:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(a,0); var bad:Vec<MirFunctionClauseMetadata>=vec_new<MirFunctionClauseMetadata>(a,2); print(lower_function_clause_metadata(source,clauses,operands,empty,bad));
 drop(bad); drop(empty); drop(out); drop(catalog); drop(operands); drop(clauses); drop(tokens); drop(source); }} return 0; }}
'''

def project(tmp_path):
    root=tmp_path/'clause_metadata'; shutil.copytree(PROJECT,root,ignore=shutil.ignore_patterns('build'))
    p=root/'src/lexer.mrt'; text=p.read_text(); text,n=re.subn(r'\nfn main\(\) -> i32 \{','\nfn fixture_main() -> i32 {',text,count=1); assert n==1; p.write_text(text)
    (root/'src/clause_metadata_probe.mrt').write_text(probe()); m=root/'Merit.toml'; text=m.read_text().replace('entry = "src/lexer.mrt"','entry = "src/clause_metadata_probe.mrt"'); m.write_text(text); return load_project(m),root

def ints(text): return [int(x) for x in text.splitlines()]

def test_clause_metadata_is_semantic_and_native(tmp_path):
    p,root=project(tmp_path); values=ints(interpret(p)); assert values[:3]==[0,0,2]
    assert values[3:8]==[1,0,0,4,-1]
    assert values[8:13]==[2,1,0,5,42]
    assert values[13]==3
    _,_,exe=build(p,root/'native'); native=subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout; assert ints(native)==values
