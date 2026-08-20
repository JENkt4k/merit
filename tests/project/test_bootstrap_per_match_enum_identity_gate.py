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
    "enum Alpha { A0, A1 }\n"
    "enum Beta { B0, B1 }\n"
    "fn compute()->i64 { let a:Alpha=0; let b:Beta=0; "
    "match (a) { A0 => { } A1 => { } } "
    "match (b) { B0 => { } B1 => { } } return 0; }\n"
)


def _probe() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    a0, a1, b0, b1 = (SOURCE.index(x) for x in ("A0", "A1", "B0", "B1"))
    return f'''module per_match_enum_identity_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_structure;
import bootstrap_statement_semantics;

capability allocate;

fn main()->i32 {{
    with capability allocate {{
        let allocator:Allocator=system_allocator();
        let source:Buffer=buffer_from_string(allocator,"{escaped}");
        let tokens:Vec<Token>=lex(source,allocator);
        let statements:Vec<StatementRecord>=parse_statement_records(source,tokens,allocator);
        var arms:Vec<MatchArmRecord>=vec_new<MatchArmRecord>(allocator,8);
        print(lower_match_arm_records(source,tokens,statements,arms));
        print(vec_len<MatchArmRecord>(arms));

        var catalog:Vec<EnumVariantCatalogEntry>=vec_new<EnumVariantCatalogEntry>(allocator,4);
        vec_push<EnumVariantCatalogEntry>(catalog,EnumVariantCatalogEntry{{enum_id:0,variant_id:0,ordinal:0,name_start:{a0},name_length:2,payload_owned:0}});
        vec_push<EnumVariantCatalogEntry>(catalog,EnumVariantCatalogEntry{{enum_id:0,variant_id:1,ordinal:1,name_start:{a1},name_length:2,payload_owned:0}});
        vec_push<EnumVariantCatalogEntry>(catalog,EnumVariantCatalogEntry{{enum_id:1,variant_id:2,ordinal:0,name_start:{b0},name_length:2,payload_owned:0}});
        vec_push<EnumVariantCatalogEntry>(catalog,EnumVariantCatalogEntry{{enum_id:1,variant_id:3,ordinal:1,name_start:{b1},name_length:2,payload_owned:0}});

        var identities:Vec<MatchEnumIdentity>=vec_new<MatchEnumIdentity>(allocator,2);
        if(vec_len<MatchArmRecord>(arms)==4){{
            let first:MatchArmRecord=vec_get<MatchArmRecord>(arms,0);
            let third:MatchArmRecord=vec_get<MatchArmRecord>(arms,2);
            vec_push<MatchEnumIdentity>(identities,MatchEnumIdentity{{match_statement:match_arm_statement(first),enum_id:0}});
            vec_push<MatchEnumIdentity>(identities,MatchEnumIdentity{{match_statement:match_arm_statement(third),enum_id:1}});
        }}

        var resolved:Vec<ResolvedMatchArm>=vec_new<ResolvedMatchArm>(allocator,8);
        print(resolve_match_arms_by_identity(source,arms,catalog,identities,resolved));
        print(vec_len<ResolvedMatchArm>(resolved));
        var index:i64=0;
        while(index<vec_len<ResolvedMatchArm>(resolved)){{
            let arm:ResolvedMatchArm=vec_get<ResolvedMatchArm>(resolved,index);
            print(resolved_match_enum_id(arm));
            index=checked_add(index,1);
        }}

        drop(resolved); drop(identities); drop(catalog); drop(arms); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "per_match_enum_identity"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer.read_text(), count=1)
    assert count == 1
    lexer.write_text(text)
    (root / "src" / "per_match_enum_identity_probe.mrt").write_text(_probe())
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text().replace(
        'entry = "src/lexer.mrt"', 'entry = "src/per_match_enum_identity_probe.mrt"'
    ))
    return load_project(manifest), root


def _values(text: str) -> list[int]:
    return [int(value) for value in text.splitlines()]


def test_per_match_enum_identity_resolves_two_matches_against_different_enums(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _values(interpret(project))
    assert interpreted == [0, 4, 0, 4, 0, 0, 1, 1]

    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _values(native) == interpreted
