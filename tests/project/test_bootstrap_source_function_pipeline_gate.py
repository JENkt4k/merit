from __future__ import annotations

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
    "capability clock;\n"
    "fn compute()->i64\n"
    "requires_caps [clock]\n"
    "requires 1 < 2;\n"
    "ensures 2 > 1;\n"
    "{ let x:i64=1+2; if x>2 { return 7; } else { return 0; } }\n"
)


def _probe() -> str:
    escaped = SOURCE.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    clock = SOURCE.index("clock")
    return f'''module source_function_pipeline_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_statements;
import bootstrap_statement_semantics;
import bootstrap_mir_functions;
import bootstrap_mir_structured_lowering;
import bootstrap_mir_function_clause_metadata;
import bootstrap_mir_function_contracts;
import bootstrap_mir_source_function_pipeline;

capability allocate;

fn main()->i32 {{
    with capability allocate {{
        let a: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(a, "{escaped}");
        let tokens: Vec<Token> = lex(source, a);
        let statements: Vec<StatementRecord> = parse_statement_records(source, tokens, a);
        let operands: Vec<StatementOperand> = parse_statement_operands(source, tokens, a);
        var catalog: Vec<CapabilityCatalogEntry> = vec_new<CapabilityCatalogEntry>(a, 1);
        vec_push<CapabilityCatalogEntry>(catalog, CapabilityCatalogEntry{{capability_id:42,name_start:{clock},name_length:5}});
        var enum_catalog: Vec<EnumVariantCatalogEntry> = vec_new<EnumVariantCatalogEntry>(a, 0);
        var struct_catalog: Vec<I64StructCatalogEntry> = vec_new<I64StructCatalogEntry>(a, 0);
        var resolved_arms: Vec<ResolvedMatchArm> = vec_new<ResolvedMatchArm>(a, 0);
        var body: Vec<MirFunctionRecord> = vec_new<MirFunctionRecord>(a, 64);
        var events: Vec<MirLowerEvent> = vec_new<MirLowerEvent>(a, 64);
        var metadata: Vec<MirFunctionClauseMetadata> = vec_new<MirFunctionClauseMetadata>(a, 8);
        var contracts: Vec<MirFunctionContractRecord> = vec_new<MirFunctionContractRecord>(a, 32);
        print(lower_source_function_semantics(source,tokens,statements,operands,enum_catalog,struct_catalog,resolved_arms,catalog,a,body,events,metadata,contracts));
        print(vec_len<MirFunctionRecord>(body));
        print(vec_len<MirLowerEvent>(events));
        print(vec_len<MirFunctionClauseMetadata>(metadata));
        print(vec_len<MirFunctionContractRecord>(contracts));
        var i:i64=0;
        while(i<vec_len<MirFunctionClauseMetadata>(metadata)){{
            let v:MirFunctionClauseMetadata=vec_get<MirFunctionClauseMetadata>(metadata,i);
            print(clause_metadata_kind(v)); print(clause_metadata_semantic_id(v));
            i=checked_add(i,1);
        }}
        var checks:i64=0; i=0;
        while(i<vec_len<MirFunctionContractRecord>(contracts)){{
            let v:MirFunctionContractRecord=vec_get<MirFunctionContractRecord>(contracts,i);
            if(function_contract_kind(v)==4){{checks=checked_add(checks,1);}}
            i=checked_add(i,1);
        }}
        print(checks);
        var branches:i64=0; var returns:i64=0; i=0;
        while(i<vec_len<MirLowerEvent>(events)){{
            let e:MirLowerEvent=vec_get<MirLowerEvent>(events,i);
            if(lower_event_kind(e)==10){{branches=checked_add(branches,1);}}
            if(lower_event_kind(e)==2){{returns=checked_add(returns,1);}}
            i=checked_add(i,1);
        }}
        print(branches); print(returns);
        drop(contracts); drop(metadata); drop(events); drop(body); drop(catalog); drop(operands); drop(statements); drop(tokens); drop(source);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "source_function_pipeline"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer = root / "src" / "lexer.mrt"
    text = lexer.read_text(encoding="utf-8")
    text, count = re.subn(r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", text, count=1)
    assert count == 1
    lexer.write_text(text, encoding="utf-8")
    (root / "src" / "source_function_pipeline_probe.mrt").write_text(_probe(), encoding="utf-8")
    manifest = root / "Merit.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        'entry = "src/lexer.mrt"', 'entry = "src/source_function_pipeline_probe.mrt"'
    ), encoding="utf-8")
    return load_project(manifest), root


def _values(text: str) -> list[int]:
    return [int(value) for value in text.splitlines()]


def test_real_source_function_body_and_clauses_share_one_native_entrypoint(tmp_path):
    project, root = _project(tmp_path)
    interpreted = _values(interpret(project))
    assert interpreted[0] == 0
    assert interpreted[1] > 0
    assert interpreted[2] > 0
    assert interpreted[3] == 1
    assert interpreted[4] > 0
    assert interpreted[5:7] == [2, 42]
    assert interpreted[7] == 2
    assert interpreted[8] >= 1
    assert interpreted[9] >= 2

    _, _, executable = build(project, root / "native")
    native = subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout
    assert _values(native) == interpreted
