from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess

from merit.project.build import build, interpret
from merit.project.loader import load_project


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "examples" / "projects" / "bootstrap_lexer"

DECLARATIONS = (
    "struct Pair<T, U> { first:T; second:U; }",
    "enum Option<T> { Some(T), None }",
    "fn identity<T: Copy + Display>(value:T)->T { return value; }",
    "trait Summarized { fn score(value:Self)->i32; }",
    "trait Described { fn show(value:Self)->i32; }",
    "impl Summarized for Point { fn score(value:Point)->i32 { return value.x; } }",
    "impl Described for Point { fn show(value:Point)->i32 { return value.x; } }",
)


def _source(declarations: tuple[str, ...]) -> str:
    return "module demo\nstruct Point { x:i32; }\n" + "\n".join(declarations) + "\nfn main()->i32{return 0;}\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _probe() -> str:
    first_source = _source(DECLARATIONS)
    second_source = _source(tuple(reversed(DECLARATIONS)))
    first = _escape(first_source)
    second = _escape(second_source)
    return f'''module bootstrap_mir_generic_catalog_probe
import bootstrap_tokens;
import bootstrap_lexer_core;
import bootstrap_mir_generic_catalog;

capability allocate;

fn print_span(borrow source:Buffer,start:i64,length:i64)->i32 {{
    print(length); var offset:i64=0;
    while(offset<length){{print(buffer_get(source,checked_add(start,offset)));offset=checked_add(offset,1);}}
    return 0;
}}

fn observe(source_text:String,i32_start:i64,allocator:Allocator)->i32 requires_caps [allocate] {{
    let source:Buffer=buffer_from_string(allocator,source_text);
    let tokens:Vec<Token>=lex(source,allocator);
    var declarations:Vec<GenericDeclarationIdentity>=vec_new<GenericDeclarationIdentity>(allocator,4);
    var parameters:Vec<GenericParameterIdentity>=vec_new<GenericParameterIdentity>(allocator,8);
    var bounds:Vec<GenericBoundIdentity>=vec_new<GenericBoundIdentity>(allocator,8);
    var traits:Vec<TraitDeclarationIdentity>=vec_new<TraitDeclarationIdentity>(allocator,4);
    var implementations:Vec<TraitImplementationIdentity>=vec_new<TraitImplementationIdentity>(allocator,4);
    var trait_methods:Vec<TraitMethodIdentity>=vec_new<TraitMethodIdentity>(allocator,4);
    var implementation_methods:Vec<TraitImplementationMethodIdentity>=vec_new<TraitImplementationMethodIdentity>(allocator,4);
    let status:i32=derive_generic_identity_catalog(
        source,tokens,allocator,declarations,parameters,bounds,traits,implementations,trait_methods,implementation_methods
    );
    print(status); print(vec_len<GenericDeclarationIdentity>(declarations));
    print(vec_len<GenericParameterIdentity>(parameters)); print(vec_len<GenericBoundIdentity>(bounds));
    print(vec_len<TraitDeclarationIdentity>(traits)); print(vec_len<TraitImplementationIdentity>(implementations));
    var index:i64=0;
    while(index<vec_len<GenericDeclarationIdentity>(declarations)){{
        let value:GenericDeclarationIdentity=vec_get<GenericDeclarationIdentity>(declarations,index);
        print(generic_declaration_kind(value));print(generic_declaration_id(value));
        print(generic_declaration_parameter_count(value));
        print_span(source,generic_declaration_name_start(value),generic_declaration_name_length(value));
        index=checked_add(index,1);
    }}
    index=0;
    while(index<vec_len<GenericParameterIdentity>(parameters)){{
        let value:GenericParameterIdentity=vec_get<GenericParameterIdentity>(parameters,index);
        print(generic_parameter_declaration_id(value));print(generic_parameter_ordinal(value));
        print(generic_parameter_bound_count(value));
        print_span(source,generic_parameter_name_start(value),generic_parameter_name_length(value));
        index=checked_add(index,1);
    }}
    index=0;
    while(index<vec_len<GenericBoundIdentity>(bounds)){{
        let value:GenericBoundIdentity=vec_get<GenericBoundIdentity>(bounds,index);
        print(generic_bound_declaration_id(value));print(generic_bound_parameter_ordinal(value));print(generic_bound_ordinal(value));
        print_span(source,generic_bound_trait_start(value),generic_bound_trait_length(value));
        index=checked_add(index,1);
    }}
    index=0;
    while(index<vec_len<TraitDeclarationIdentity>(traits)){{
        let value:TraitDeclarationIdentity=vec_get<TraitDeclarationIdentity>(traits,index);
        print(trait_declaration_id(value));
        print_span(source,trait_declaration_name_start(value),trait_declaration_name_length(value));
        index=checked_add(index,1);
    }}
    index=0;
    while(index<vec_len<TraitImplementationIdentity>(implementations)){{
        let value:TraitImplementationIdentity=vec_get<TraitImplementationIdentity>(implementations,index);
        print(trait_implementation_id(value));print(trait_implementation_trait_id(value));
        print_span(source,trait_implementation_trait_start(value),trait_implementation_trait_length(value));
        print_span(source,trait_implementation_target_start(value),trait_implementation_target_length(value));
        index=checked_add(index,1);
    }}
    let copy_bound:GenericBoundIdentity=vec_get<GenericBoundIdentity>(bounds,0);
    let implementation:TraitImplementationIdentity=vec_get<TraitImplementationIdentity>(implementations,0);
    let pair:GenericDeclarationIdentity=vec_get<GenericDeclarationIdentity>(declarations,1);
    print(generic_type_implements_trait(
        source,i32_start,3,source,generic_bound_trait_start(copy_bound),generic_bound_trait_length(copy_bound),traits,implementations
    ));
    print(generic_type_implements_trait(
        source,trait_implementation_target_start(implementation),trait_implementation_target_length(implementation),source,
        generic_bound_trait_start(copy_bound),generic_bound_trait_length(copy_bound),traits,implementations
    ));
    print(generic_type_implements_trait(
        source,trait_implementation_target_start(implementation),trait_implementation_target_length(implementation),source,
        trait_implementation_trait_start(implementation),trait_implementation_trait_length(implementation),traits,implementations
    ));
    print(generic_type_implements_trait(
        source,generic_declaration_name_start(pair),generic_declaration_name_length(pair),source,
        trait_implementation_trait_start(implementation),trait_implementation_trait_length(implementation),traits,implementations
    ));
    drop(implementation_methods);drop(trait_methods);drop(implementations);drop(traits);drop(bounds);drop(parameters);drop(declarations);drop(tokens);drop(source);
    return status;
}}

fn main()->i32 {{
    with capability allocate {{
        let allocator:Allocator=system_allocator();
        observe("{first}",{first_source.index("i32")},allocator);
        observe("{second}",{second_source.index("i32")},allocator);
    }}
    return 0;
}}
'''


def _project(tmp_path: Path):
    root = tmp_path / "generic_catalog"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("build"))
    lexer_path = root / "src" / "lexer.mrt"
    lexer = lexer_path.read_text(encoding="utf-8")
    lexer, replacements = re.subn(
        r"\nfn main\(\) -> i32 \{", "\nfn fixture_main() -> i32 {", lexer, count=1
    )
    assert replacements == 1
    lexer_path.write_text(lexer, encoding="utf-8")
    (root / "src" / "generic_catalog_probe.mrt").write_text(_probe(), encoding="utf-8")
    manifest = root / "Merit.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'entry = "src/lexer.mrt"', 'entry = "src/generic_catalog_probe.mrt"'
        ),
        encoding="utf-8",
    )
    return root, load_project(manifest)


def test_generic_trait_impl_identities_are_native_and_source_order_independent(tmp_path: Path):
    root, project = _project(tmp_path)
    interpreted = interpret(project)
    _, _, executable = build(project, root / "native")
    native = subprocess.run(
        [str(executable)], check=True, text=True, capture_output=True
    ).stdout
    assert native == interpreted
    lines = native.splitlines()
    assert lines[:6] == ["0", "3", "4", "2", "2", "2"]
    assert len(lines) % 2 == 0
    midpoint = len(lines) // 2
    assert lines[:midpoint] == lines[midpoint:]
