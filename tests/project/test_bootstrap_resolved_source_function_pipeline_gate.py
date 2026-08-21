from pathlib import Path
import re
import shutil
import subprocess

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
    "{ let a:Resource=1; let flag:i64=1; match flag { Left(x) => { drop(a); return 1; } "
    "Right(y) => { drop(a); } Other(z) => { drop(a); } } with capability clock { return 2; } }\n"
)


def _probe() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    left, right, other, clock = (SOURCE.index(x) for x in ("Left", "Right", "Other", "clock"))
    return f'''module resolved_source_function_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_semantics;
import bootstrap_mir_functions;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_function_clause_metadata;
import bootstrap_mir_function_contracts;
import bootstrap_mir_match_capability_flow;
import bootstrap_mir_ownership_flow;
import bootstrap_mir_resolved_source_function_pipeline;

capability allocate;

fn main()->i32 {{
    with capability allocate {{
        let allocator:Allocator=system_allocator();
        let source:Buffer=buffer_from_string(allocator,"{escaped}");
        let tokens:Vec<Token>=lex(source,allocator);
        let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
        let operands:Vec<StatementOperand>=parse_statement_operands(source,tokens,allocator);

        var variants:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,3);
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:7,variant_id:70,ordinal:0,name_start:{left},name_length:4,payload_owned:0}});
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:7,variant_id:71,ordinal:1,name_start:{right},name_length:5,payload_owned:0}});
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:7,variant_id:72,ordinal:2,name_start:{other},name_length:5,payload_owned:0}});
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
        var canonical:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,128);
        var ownership_records:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,64);
        var structs:Vec<I64StructCatalogEntry>=vec_new<I64StructCatalogEntry>(allocator,0);

        print(lower_resolved_source_function_semantics(
            source,tokens,statements,operands,variants,structs,7,capabilities,bindings,allocator,
            body,metadata,contracts,arms,scopes,ownership_events,effects,canonical,ownership_records
        ));
        print(vec_len<MirFunctionRecord>(body));
        print(vec_len<ResolvedMatchArm>(arms));
        print(vec_len<ResolvedCapabilityScope>(scopes));
        print(vec_len<MirCapabilityEffect>(effects));
        print(vec_len<MirFunctionClauseMetadata>(metadata));
        print(vec_len<MirFunctionContractRecord>(contracts));
        print(validate_ownership_records(ownership_records,bindings));

        var required:i64=-1;
        var i:i64=0;
        while(i<vec_len<MirFunctionClauseMetadata>(metadata)){{
            let value:MirFunctionClauseMetadata=vec_get<MirFunctionClauseMetadata>(metadata,i);
            if(clause_metadata_kind(value)==2){{required=clause_metadata_semantic_id(value);}}
            i=checked_add(i,1);
        }}
        print(required);
        i=0;
        while(i<vec_len<MirCapabilityEffect>(effects)){{
            let value:MirCapabilityEffect=vec_get<MirCapabilityEffect>(effects,i);
            print(capability_effect_kind(value)); print(capability_effect_id(value));
            i=checked_add(i,1);
        }}
        var matches:i64=0; var cases:i64=0; var defaults:i64=0; var unreachable:i64=0; var returns:i64=0;
        i=0;
        while(i<vec_len<MirLowerEvent>(canonical)){{
            let event:MirLowerEvent=vec_get<MirLowerEvent>(canonical,i);
            let kind:i32=lower_event_kind(event);
            if(kind==30){{matches=checked_add(matches,1);}}
            if(kind==31){{cases=checked_add(cases,1);}}
            if(kind==32){{defaults=checked_add(defaults,1);}}
            if(kind==3){{unreachable=checked_add(unreachable,1);}}
            if(kind==2){{returns=checked_add(returns,1);}}
            i=checked_add(i,1);
        }}
        print(matches); print(cases); print(defaults); print(unreachable); print(returns);

        drop(ownership_records); drop(canonical); drop(effects); drop(ownership_events);
        drop(scopes); drop(arms); drop(contracts); drop(metadata); drop(body);
        drop(bindings); drop(capabilities); drop(variants); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "resolved_source_function"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "resolved_source_function_probe.mrt").write_text(_probe())
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text().replace(
        'entry = "src/lexer.mrt"', 'entry = "src/resolved_source_function_probe.mrt"'
    ))
    return load_project(manifest), root


def _values(text: str) -> list[int]:
    return [int(value) for value in text.splitlines()]


def test_resolved_function_source_unifies_match_capability_clauses_and_ownership(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _values(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] > 0
    assert interpreted[2:5] == [3, 1, 2]
    assert interpreted[5] >= 1
    assert interpreted[6] > 0
    assert interpreted[7] == 0
    assert interpreted[8] == 9
    assert interpreted[9:13] == [1, 9, 2, 9]
    assert interpreted[13:18] == [1, 3, 1, 1, 2]

    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _values(native) == interpreted
