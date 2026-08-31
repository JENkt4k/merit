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
    "enum OtherChoice { First(i64), Second(i64) }\n"
    "enum Choice { Left(i64), Right(i64) }\n"
    "fn compute()->i64 { let flag:Choice=1; match (flag) { "
    "Left(x) => { return 7; } Right(y) => { } } return 8; }\n"
)


def _probe() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    other_choice = SOURCE.index("OtherChoice")
    choice = SOURCE.index("Choice", other_choice + len("OtherChoice"))
    first, second, left, right = (SOURCE.index(x) for x in ("First", "Second", "Left", "Right"))
    return f'''module match_subject_enum_identity_probe
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

        var variants:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,4);
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:0,enum_name_start:{other_choice},enum_name_length:11,variant_id:0,ordinal:0,name_start:{first},name_length:5,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:0,enum_name_start:{other_choice},enum_name_length:11,variant_id:1,ordinal:1,name_start:{second},name_length:6,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:1,enum_name_start:{choice},enum_name_length:6,variant_id:2,ordinal:0,name_start:{left},name_length:4,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
        vec_push<EnumVariantCatalogEntry>(variants,EnumVariantCatalogEntry{{enum_id:1,enum_name_start:{choice},enum_name_length:6,variant_id:3,ordinal:1,name_start:{right},name_length:5,payload_owned:0,payload_type_code:function_mir_i64_type_code()}});
        var capabilities:Vec<CapabilityCatalogEntry>=vec_new<CapabilityCatalogEntry>(allocator,0);
        var bindings:Vec<MirOwnershipBinding>=vec_new<MirOwnershipBinding>(allocator,1);
        vec_push<MirOwnershipBinding>(bindings,ownership_binding(0,0,0,0));

        var body:Vec<MirFunctionRecord>=vec_new<MirFunctionRecord>(allocator,64);
        var metadata:Vec<MirFunctionClauseMetadata>=vec_new<MirFunctionClauseMetadata>(allocator,4);
        var contracts:Vec<MirFunctionContractRecord>=vec_new<MirFunctionContractRecord>(allocator,8);
        var arms:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(allocator,4);
        var scopes:Vec<ResolvedCapabilityScope>=vec_new<ResolvedCapabilityScope>(allocator,0);
        var ownership_events:Vec<MirOwnershipEvent>=vec_new<MirOwnershipEvent>(allocator,64);
        var effects:Vec<MirCapabilityEffect>=vec_new<MirCapabilityEffect>(allocator,0);
        var canonical:Vec<MirLowerEvent>=vec_new<MirLowerEvent>(allocator,96);
        var ownership_records:Vec<MirOwnershipRecord>=vec_new<MirOwnershipRecord>(allocator,32);
        var structs:Vec<I64StructCatalogEntry>=vec_new<I64StructCatalogEntry>(allocator,0);

        print(lower_resolved_source_function_semantics(
            source,tokens,statements,operands,variants,structs,-1,capabilities,bindings,allocator,
            body,metadata,contracts,arms,scopes,ownership_events,effects,canonical,ownership_records
        ));
        print(vec_len<ResolvedMatchArm>(arms));
        if(vec_len<ResolvedMatchArm>(arms)==2){{
            let first_arm:ResolvedMatchArm=vec_get<ResolvedMatchArm>(arms,0);
            let second_arm:ResolvedMatchArm=vec_get<ResolvedMatchArm>(arms,1);
            print(resolved_match_enum_id(first_arm));
            print(resolved_match_enum_id(second_arm));
        }}

        drop(ownership_records); drop(canonical); drop(effects); drop(ownership_events);
        drop(scopes); drop(arms); drop(contracts); drop(metadata); drop(body);
        drop(bindings); drop(capabilities); drop(variants); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "match_subject_enum_identity"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "match_subject_enum_identity_probe.mrt").write_text(_probe())
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text().replace(
        'entry = "src/lexer.mrt"', 'entry = "src/match_subject_enum_identity_probe.mrt"'
    ))
    return load_project(manifest), root


def _values(text: str) -> list[int]:
    return [int(value) for value in text.splitlines()]


def test_match_subject_declared_type_selects_enum_identity_with_multiple_enums(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _values(interpret(project))
    assert interpreted == [0, 2, 1, 1]

    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _values(native) == interpreted
