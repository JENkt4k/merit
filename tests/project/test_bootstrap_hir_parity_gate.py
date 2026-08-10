from __future__ import annotations
import importlib.util,json
from pathlib import Path
import re,shutil,subprocess
from merit.bootstrap.ast_contract import lower_expression_ast
from merit.bootstrap.hir_contract import HirType
from merit.bootstrap.hir_expression import HirConstructorSignature,HirFieldSignature,HirFunctionSignature,lower_resolved_expression_hir
from merit.bootstrap.hir_parity import primitive_hir_parity_observations
from merit.bootstrap.parity import build_parity_report,markdown_summary
from merit.bootstrap.repository_corpus import load_repository_corpus
from merit.project.build import build,interpret
from merit.project.loader import load_project
ROOT=Path(__file__).resolve().parents[2]; PROJECT=ROOT/"examples/projects/bootstrap_lexer"; MANIFEST=ROOT/"tests/project/bootstrap_corpus_v1.json"; REFERENCE_PATH=Path(__file__).with_name("test_bootstrap_lexer.py")
I64=HirType("i64"); ACCOUNT=HirType("Account"); RECORD=HirType("Record"); POINT=HirType("Point")
def _load_reference_module():
 s=importlib.util.spec_from_file_location("merit_bootstrap_hir_parity_reference",REFERENCE_PATH); assert s is not None and s.loader is not None; m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
REFERENCE=_load_reference_module()
def _case_semantics(case_id):
 bindings=(); functions=(); fields=(); constructors=(); type_names={}; constructor_fields={}; case_kind=0
 if case_id=="left-associative-subtract": bindings=(("a",I64),("b",I64),("c",I64))
 elif case_id=="comparison-last": bindings=(("a",I64),("b",I64))
 elif case_id=="division-before-addition": bindings=(("a",I64),)
 elif case_id=="empty-call": functions=(HirFunctionSignature("f",(),I64),); case_kind=1
 elif case_id=="argument-sequence": functions=(HirFunctionSignature("f",(I64,I64),I64),); case_kind=2
 elif case_id=="field-before-addition": bindings=(("account",ACCOUNT),); fields=(HirFieldSignature(ACCOUNT,"balance",I64),); type_names={3:ACCOUNT}; case_kind=3
 elif case_id=="nested-call-field": functions=(HirFunctionSignature("g",(I64,),I64),HirFunctionSignature("f",(I64,),RECORD)); fields=(HirFieldSignature(RECORD,"value",I64),); type_names={4:RECORD}; case_kind=4
 elif case_id=="direct-constructor-field": constructors=(HirConstructorSignature("Point",POINT,(("x",I64),("y",I64))),); fields=(HirFieldSignature(POINT,"x",I64),); type_names={5:POINT}; constructor_fields={"Point":("x","y")}; case_kind=5
 return bindings,functions,fields,constructors,type_names,constructor_fields,case_kind
def _probe_source(cases):
 calls=[]
 for index,case in enumerate(cases):
  *_,case_kind=_case_semantics(case.case_id); literal=json.dumps(case.text); calls.append(f"        let source_{index}: Buffer = buffer_from_string(allocator, {literal});\n        emit_hir_case(source_{index}, allocator, {case_kind});\n        drop(source_{index});")
 body="\n".join(calls)
 return f'''module bootstrap_hir_parity_probe
import bootstrap_tokens; import bootstrap_syntax; import bootstrap_lexer_core; import bootstrap_hir;
capability allocate;
fn ast_identifier_is_symbol(borrow ast_nodes:Vec<AstNodeRecord>,index:i64)->i32 {{ var parent_index:i64=0; while(parent_index<vec_len<AstNodeRecord>(ast_nodes)){{let parent:AstNodeRecord=vec_get<AstNodeRecord>(ast_nodes,parent_index); if(ast_kind(parent)==34){{if(ast_left(parent)==index){{return 1;}}}} if(ast_kind(parent)==35){{if(ast_right(parent)==index){{return 1;}}}} if(ast_kind(parent)==38){{if(ast_left(parent)==index){{return 1;}}}} if(ast_kind(parent)==70){{if(ast_left(parent)==index){{return 1;}}}} parent_index=checked_add(parent_index,1);}} return 0; }}
fn resolved_hir_type_code(borrow ast_nodes:Vec<AstNodeRecord>,index:i64,case_kind:i32)->i32 {{ let ast:AstNodeRecord=vec_get<AstNodeRecord>(ast_nodes,index); if(ast_group_parent(ast)>=0){{return 1;}} if(ast_kind(ast)==37){{return 0;}} if(ast_kind(ast)==38){{return 0;}} if(ast_kind(ast)==30){{if(ast_identifier_is_symbol(ast_nodes,index)){{return 0;}} if(case_kind==3){{return 3;}} return 1;}} if(ast_kind(ast)==34){{if(case_kind==4){{let callee:AstNodeRecord=vec_get<AstNodeRecord>(ast_nodes,ast_left(ast));if(ast_start(callee)==0){{return 4;}}}} return 1;}} if(ast_kind(ast)==70){{if(case_kind==5){{return 5;}}}} if(ast_kind(ast)==35){{return 1;}} if(ast_kind(ast)>=40){{if(ast_kind(ast)<=45){{return 2;}}}} return 1; }}
fn emit_hir_case(borrow source:Buffer,allocator:Allocator,case_kind:i32)->i32 requires_caps [allocate] {{ let tokens:Vec<Token>=lex(source,allocator); let expressions:Vec<ExpressionNode>=parse_expression_tokens(source,tokens,allocator); let ast_nodes:Vec<AstNodeRecord>=lower_expression_ast_records(expressions,allocator); var hir_nodes:Vec<HirExpressionRecord>=vec_new<HirExpressionRecord>(allocator,vec_len<AstNodeRecord>(ast_nodes)); var binding_starts:Vec<i64>=vec_new<i64>(allocator,4); var binding_lengths:Vec<i64>=vec_new<i64>(allocator,4); var ast_index:i64=0; while(ast_index<vec_len<AstNodeRecord>(ast_nodes)){{let ast:AstNodeRecord=vec_get<AstNodeRecord>(ast_nodes,ast_index);var binding_id:i64=-1;if(ast_kind(ast)==30){{if(ast_group_parent(ast)<0){{if(ast_identifier_is_symbol(ast_nodes,ast_index)){{binding_id=-2;}}else{{binding_id=hir_find_binding_id(source,binding_starts,binding_lengths,ast_start(ast),ast_length(ast));if(binding_id<0){{binding_id=vec_len<i64>(binding_starts);vec_push<i64>(binding_starts,ast_start(ast));vec_push<i64>(binding_lengths,ast_length(ast));}}}}}}}} let hir:HirExpressionRecord=lower_resolved_hir_record(ast_kind(ast),ast_start(ast),ast_length(ast),ast_left(ast),ast_right(ast),ast_group_start(ast),ast_group_length(ast),ast_group_parent(ast),binding_id,resolved_hir_type_code(ast_nodes,ast_index,case_kind));vec_push<HirExpressionRecord>(hir_nodes,hir);ast_index=checked_add(ast_index,1);}} print(validate_primitive_hir_records(hir_nodes));print(vec_len<HirExpressionRecord>(hir_nodes));var index:i64=0;while(index<vec_len<HirExpressionRecord>(hir_nodes)){{let node:HirExpressionRecord=vec_get<HirExpressionRecord>(hir_nodes,index);print(hir_kind(node));print(hir_start(node));print(hir_length(node));print(hir_left(node));print(hir_right(node));print(hir_symbol(node));print(hir_type_code(node));print(hir_numeric_policy(node));print(hir_binding_id(node));index=checked_add(index,1);}} drop(binding_lengths);drop(binding_starts);drop(hir_nodes);drop(ast_nodes);drop(expressions);drop(tokens);return 0; }}
fn main()->i32 {{ with capability allocate {{ let allocator:Allocator=system_allocator();
{body}
 }} return 0; }}
'''
def _project_with_probe(tmp_path,cases):
 project_root=tmp_path/"bootstrap_hir_parity"; shutil.copytree(PROJECT,project_root,ignore=shutil.ignore_patterns("build")); lexer_path=project_root/"src/lexer.mrt"; lexer=lexer_path.read_text(encoding="utf-8"); lexer,replacements=re.subn(r"\nfn main\(\) -> i32 \{","\nfn fixture_main() -> i32 {",lexer,count=1); assert replacements==1; lexer_path.write_text(lexer,encoding="utf-8"); (project_root/"src/hir_parity_probe.mrt").write_text(_probe_source(cases),encoding="utf-8"); manifest=project_root/"Merit.toml"; text=manifest.read_text(encoding="utf-8").replace('entry = "src/lexer.mrt"','entry = "src/hir_parity_probe.mrt"'); manifest.write_text(text,encoding="utf-8"); return load_project(manifest),project_root
def _parse_probe_output(output,case_count):
 values=[int(v) for v in output.splitlines()]; cursor=0; cases=[]
 for _ in range(case_count):
  validation=values[cursor]; count=values[cursor+1]; cursor+=2; fields=values[cursor:cursor+count*9]; cursor+=count*9; cases.append((validation,[tuple(fields[i:i+9]) for i in range(0,len(fields),9)]))
 assert cursor==len(values); return cases
def _reference_hir(case):
 ast=lower_expression_ast(REFERENCE.reference_expression(case.text)); bindings,functions,fields,constructors,_,_,_=_case_semantics(case.case_id); return lower_resolved_expression_hir(ast,case.text,expected_type=I64,bindings=bindings,functions=functions,fields=fields,constructors=constructors,module_name=case.case_id)
def _observations(cases,actual):
 observations=[]
 for case,(validation,records) in zip(cases,actual,strict=True):
  assert validation==0,case.case_id; *_,type_names,constructor_fields,_=_case_semantics(case.case_id); observations.extend(primitive_hir_parity_observations(case.case_id,_reference_hir(case),records,case.text,type_names=type_names,constructor_fields=constructor_fields))
 return observations
def test_repository_resolved_expression_hir_has_real_interpreter_and_native_parity(tmp_path):
 corpus=load_repository_corpus(MANIFEST); cases=corpus.for_stage("hir"); assert len(cases)==10; assert cases[-1].case_id=="direct-constructor-field"; project,project_root=_project_with_probe(tmp_path,cases); interpreted=_parse_probe_output(interpret(project),len(cases)); report=build_parity_report(corpus,_observations(cases,interpreted),stages=["hir"]); assert report.complete,markdown_summary(report); assert report.stage_counts()=={"hir":(10,10)}; _,_,executable=build(project,project_root/"hir_parity"); native=_parse_probe_output(subprocess.run([str(executable)],cwd=project_root,check=True,capture_output=True,text=True).stdout,len(cases)); assert native==interpreted; native_report=build_parity_report(corpus,_observations(cases,native),stages=["hir"]); assert native_report.complete,markdown_summary(native_report); assert native_report.stage_counts()=={"hir":(10,10)}
