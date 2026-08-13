from pathlib import Path
import re, shutil, subprocess
from merit.project.build import build, interpret
from merit.project.loader import load_project

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/"examples/projects/bootstrap_lexer"
CASE=ROOT/"tests/fixtures/resolved_source_case.mrt"

def _probe(source:str)->str:
    e=source.replace("\\","\\\\").replace('"','\\"').replace("\n","\\n")
    L,R,O,C=(source.index(x) for x in ("Left","Right","Other","clock"))
    return f'''module probe
import bootstrap_tokens; import bootstrap_lexer_core; import bootstrap_statements;
import bootstrap_statement_structure; import bootstrap_statement_semantics;
import bootstrap_mir_structured_lowering; import bootstrap_mir_match_capability_flow;
import bootstrap_mir_ownership_flow; import bootstrap_mir_source_ownership_lowering;
capability allocate;
fn main()->i32 {{ with capability allocate {{
let a:Allocator=system_allocator(); let s:Buffer=buffer_from_string(a,"{e}");
let t:Vec<Token>=lex(s,a); let st:Vec<StatementRecord>=parse_statement_records(s,t,a); let op:Vec<StatementOperand>=parse_statement_operands(s,t,a);
var ra:Vec<MatchArmRecord>=vec_new<MatchArmRecord>(a,4); var rs:Vec<CapabilityScopeRecord>=vec_new<CapabilityScopeRecord>(a,2);
print(lower_match_arm_records(s,t,st,ra)); print(lower_capability_scope_records(s,t,st,op,rs));
var v:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(a,3);
vec_push<EnumVariantCatalogEntry>(v,EnumVariantCatalogEntry{{enum_id:7,variant_id:70,ordinal:0,name_start:{L},name_length:4,payload_owned:0}});
vec_push<EnumVariantCatalogEntry>(v,EnumVariantCatalogEntry{{enum_id:7,variant_id:71,ordinal:1,name_start:{R},name_length:5,payload_owned:0}});
vec_push<EnumVariantCatalogEntry>(v,EnumVariantCatalogEntry{{enum_id:7,variant_id:72,ordinal:2,name_start:{O},name_length:5,payload_owned:0}});
var cc:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(a,1); vec_push<CapabilityCatalogEntry>(cc,CapabilityCatalogEntry{{capability_id:9,name_start:{C},name_length:5}});
var arms:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(a,4); var scopes:Vec<ResolvedCapabilityScope>=vec_new<ResolvedCapabilityScope>(a,2);
print(resolve_match_arms(s,ra,v,7,arms)); print(resolve_capability_scopes(s,rs,cc,scopes));
var b:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(a,2); vec_push<MirOwnershipBinding>(b,ownership_binding(0,0,1,0)); vec_push<MirOwnershipBinding>(b,ownership_binding(1,1,0,0));
var ev:Vec<MirOwnershipEvent>=vec_new<MirOwnershipEvent>(a,64); var fx:Vec<MirCapabilityEffect>=vec_new<MirCapabilityEffect>(a,4);
print(lower_resolved_source_ownership_events(s,t,st,op,b,arms,scopes,a,ev,fx)); print(vec_len<MirCapabilityEffect>(fx));
var i:i64=0; while(i<vec_len<MirCapabilityEffect>(fx)){{let x:MirCapabilityEffect=vec_get<MirCapabilityEffect>(fx,i);print(capability_effect_kind(x));print(capability_effect_id(x));i=checked_add(i,1);}}
var lo:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(a,80); var rec:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(a,48);
print(lower_ownership_flow(ev,b,a,lo,rec)); print(validate_ownership_records(rec,b)); print(vec_len<MirLowerEvent>(lo));
i=0;while(i<vec_len<MirLowerEvent>(lo)){{let x:MirLowerEvent=vec_get<MirLowerEvent>(lo,i);print(lower_event_kind(x));print(lower_event_a(x));print(lower_event_b(x));i=checked_add(i,1);}}
drop(rec);drop(lo);drop(fx);drop(ev);drop(b);drop(scopes);drop(arms);drop(cc);drop(v);drop(rs);drop(ra);drop(op);drop(st);drop(t);drop(s); }} return 0; }}'''

def _project(tmp_path):
    root=tmp_path/"resolved_source"; shutil.copytree(PROJECT,root,ignore=shutil.ignore_patterns("build"))
    p=root/"src/lexer.mrt"; text,n=re.subn(r"\nfn main\(\) -> i32 \{","\nfn fixture_main() -> i32 {",p.read_text(),count=1); assert n==1; p.write_text(text)
    (root/"src/probe.mrt").write_text(_probe(CASE.read_text()))
    m=root/"Merit.toml"; m.write_text(m.read_text().replace('entry = "src/lexer.mrt"','entry = "src/probe.mrt"'))
    return load_project(m),root

def _parse(out):
    x=[int(v) for v in out.splitlines()]; assert x[:4]==[0,0,0,0]; q=4
    source=x[q]; q+=1; nfx=x[q]; q+=1; fx=[tuple(x[q+i:q+i+2]) for i in range(0,nfx*2,2)]; q+=nfx*2
    own,val,n=x[q:q+3]; q+=3; events=[tuple(x[q+i:q+i+3]) for i in range(0,n*3,3)]; q+=n*3; assert q==len(x)
    return source,fx,own,val,events

def test_resolved_source_match_and_capability_reach_canonical_mir(tmp_path):
    project,root=_project(tmp_path); got=_parse(interpret(project))
    assert got[:4]==(0,[(1,9),(2,9)],0,0)
    kinds=[e[0] for e in got[4]]; assert 30 in kinds and kinds.count(31)==3 and 32 in kinds and 3 in kinds and 33 in kinds
    assert next(e for e in got[4] if e[0]==30)[2]==4
    assert [e[1] for e in got[4] if e[0]==31]==[0,1,2]
    _,_,exe=build(project,root/"native"); native=subprocess.run([str(exe)],check=True,text=True,capture_output=True).stdout
    assert _parse(native)==got
