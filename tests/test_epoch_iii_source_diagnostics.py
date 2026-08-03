from pathlib import Path
import json

import pytest

from merit.compiler import Checker, CompileError, main as compiler_main, mir, parse
from merit.diagnostics import diagnostic_from_exception, render_exception
from merit.project.cli import main as project_cli_main
from merit.project.loader import load_project


MOVE_SOURCE = '''module move_origin
capability allocate;
fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "origin");
        let destination: Buffer = source;
        print(buffer_len(source));
        drop(destination);
    }
    return 0;
}'''


def move_error(source=MOVE_SOURCE, source_name="move_origin.mrt"):
    with pytest.raises(CompileError) as caught:
        Checker(parse(source, source_name)).check()
    return caught.value


def semantic_error(source, source_name="semantic_error.mrt"):
    with pytest.raises(CompileError) as caught:
        Checker(parse(source, source_name)).check()
    return caught.value


def test_use_after_move_carries_primary_and_origin_spans():
    error = move_error()
    assert error.code == "M5001"
    assert (error.span.line, error.span.column, error.span.source_name) == (8, 26, "move_origin.mrt")
    assert len(error.notes) == 1
    assert error.notes[0].message == "value moved here (initializing destination)"
    assert (error.notes[0].span.line, error.notes[0].span.column) == (7, 35)


def test_rendered_move_diagnostic_shows_both_source_locations():
    rendered = render_exception(move_error(), Path("move_origin.mrt"), MOVE_SOURCE)
    assert "error[M5001]: use of moved value source" in rendered
    assert " --> move_origin.mrt:8:26" in rendered
    assert "8 |         print(buffer_len(source));" in rendered
    assert "note: value moved here (initializing destination)" in rendered
    assert " --> move_origin.mrt:7:35" in rendered
    assert "7 |         let destination: Buffer = source;" in rendered


def test_use_after_drop_reports_previous_drop_location():
    source = '''module drop_origin
capability allocate;
fn main() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let value: Buffer = buffer_from_string(allocator, "drop");
        drop(value);
        print(buffer_len(value));
    }
    return 0;
}'''
    error = move_error(source, "drop_origin.mrt")
    assert error.code == "M5103"
    assert error.span.line == 8
    assert error.notes[0].message == "value dropped here"
    assert error.notes[0].span.line == 7


def test_branch_move_origin_survives_state_merge():
    source = MOVE_SOURCE.replace(
        "let destination: Buffer = source;",
        "if 1 { let destination: Buffer = source; drop(destination); } else { }",
    ).replace("        drop(destination);\n", "")
    error = move_error(source)
    assert error.code == "M5001"
    assert error.notes[0].span.line == 7


def test_mir_exposes_consumption_source_span():
    source = MOVE_SOURCE.replace("        print(buffer_len(source));\n", "")
    program = parse(source, "move_origin.mrt")
    Checker(program).check()
    function = mir(program)["functions"][0]
    assert function["consumed_roots"] == ["source"]
    assert function["consumption_sites"]["source"] == {
        "line": 7,
        "column": 35,
        "end_line": 7,
        "end_column": 41,
        "source_name": "move_origin.mrt",
    }


def test_project_merge_retains_embedded_source_identity_without_legacy_maps():
    project = load_project(Path("examples/projects/binary_packet/Merit.toml"))
    spans = [project.program.provenance(function).primary for function in project.program.functions]
    assert spans
    source_names = {span.source_name for span in spans}
    assert str((Path("examples/projects/binary_packet/src/main.mrt")).resolve()) in source_names
    assert str((Path("examples/projects/binary_packet/src/packet.mrt")).resolve()) in source_names
    assert not hasattr(project.program, "spans")
    assert not hasattr(project.program, "related_spans")


def write_invalid_project(tmp_path):
    root = tmp_path / "move_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="move_project"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n'
    )
    (root / "src" / "main.mrt").write_text(MOVE_SOURCE.replace("module move_origin", "module move_project"))
    return root


@pytest.mark.parametrize("command", ["check", "build", "run", "verify", "audit"])
def test_project_commands_render_source_aware_semantic_errors(tmp_path, capsys, command):
    root = write_invalid_project(tmp_path)
    arguments = [command, str(root)]
    if command in ("build", "run", "verify"):
        arguments += ["-o", str(tmp_path / "invalid-output")]
    assert project_cli_main(arguments) == 1
    error = capsys.readouterr().err
    source_path = root / "src" / "main.mrt"
    assert "error[M5001]: use of moved value source" in error
    assert f" --> {source_path}:8:26" in error
    assert "note: value moved here (initializing destination)" in error
    assert f" --> {source_path}:7:35" in error


def test_single_source_cli_renders_structured_semantic_error(tmp_path, capsys):
    source = tmp_path / "move_origin.mrt"
    source.write_text(MOVE_SOURCE)
    assert compiler_main(["check", str(source)]) == 1
    error = capsys.readouterr().err
    assert "error[M5001]: use of moved value source" in error
    assert f" --> {source}:8:26" in error
    assert "note: value moved here (initializing destination)" in error


def test_multimodule_diagnostic_points_to_owning_non_entry_source(tmp_path, capsys):
    root = tmp_path / "multi_move"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="multi_move"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n'
    )
    (root / "src" / "main.mrt").write_text(
        "module multi_move\nimport worker;\nfn main() -> i32 { return 0; }\n"
    )
    worker = root / "src" / "worker.mrt"
    worker.write_text('''module worker
capability allocate;
pub fn broken() -> i32 {
    with capability allocate {
        let allocator: Allocator = system_allocator();
        let source: Buffer = buffer_from_string(allocator, "worker");
        let destination: Buffer = source;
        print(buffer_len(source));
        drop(destination);
    }
    return 0;
}''')
    assert project_cli_main(["check", str(root)]) == 1
    error = capsys.readouterr().err
    assert f" --> {worker}:8:26" in error
    assert f" --> {worker}:7:35" in error


@pytest.mark.parametrize(
    ("source", "code", "line", "excerpt"),
    [
        (
            'module typed\nfn main() -> i32 {\n    let value: i32 = "text";\n    return 0;\n}',
            "M3001",
            3,
            'let value: i32 = "text";',
        ),
        (
            'module caps\ncapability allocate;\nfn main() -> i32 {\n    let allocator: Allocator = system_allocator();\n    let value: Buffer = buffer_from_string(allocator, "text");\n    return 0;\n}',
            "M2003",
            5,
            'buffer_from_string(allocator, "text")',
        ),
        (
            'module replacement\nfn main() -> i32 {\n    var value: i64 = 1;\n    replace(value, 2);\n    return 0;\n}',
            "M5203",
            4,
            "replace(value, 2);",
        ),
        (
            'module matches\nenum Maybe { Some(i32), None }\nfn main() -> i32 {\n    let value: Maybe = None();\n    match (value) { None => { print(0); } }\n    return 0;\n}',
            "M6102",
            5,
            "match (value)",
        ),
    ],
)
def test_major_semantic_errors_have_actionable_primary_spans(source, code, line, excerpt):
    error = semantic_error(source)
    assert error.code == code
    assert (error.span.line, error.span.source_name) == (line, "semantic_error.mrt")
    rendered = render_exception(error, Path("semantic_error.mrt"), source)
    assert f"error[{code}]" in rendered
    assert f" --> semantic_error.mrt:{line}:" in rendered
    assert excerpt in rendered


def test_generated_generic_body_diagnostic_maps_to_template_source():
    source = '''module generic_origin
fn convert<T>(value: T) -> i32 {
    return value;
}
fn main() -> i32 {
    return convert<i64>(1);
}'''
    error = semantic_error(source, "generic_origin.mrt")
    assert error.code == "M3002"
    assert (error.span.line, error.span.column, error.span.source_name) == (3, 5, "generic_origin.mrt")
    assert error.notes[0].message == "generic instantiated here"
    assert (error.notes[0].span.line, error.notes[0].span.source_name) == (6, "generic_origin.mrt")
    rendered = render_exception(error, Path("generic_origin.mrt"), source)
    assert "3 |     return value;" in rendered
    assert "6 |     return convert<i64>(1);" in rendered


def test_generic_template_removal_does_not_shift_following_source_spans():
    source = '''module generic_following
fn identity<T>(value: T) -> T {
    return value;
}
fn main() -> i32 {
    let bad: i32 = "still line six";
    return 0;
}'''
    error = semantic_error(source, "generic_following.mrt")
    assert error.code == "M3001"
    assert (error.span.line, error.span.source_name) == (6, "generic_following.mrt")


def test_project_generic_diagnostic_links_template_and_instantiation_units(tmp_path, capsys):
    root = tmp_path / "generic_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="generic_project"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n'
    )
    main_source = root / "src" / "main.mrt"
    main_source.write_text('''module generic_project
import worker;
fn main() -> i32 {
    return convert<i64>(1);
}''')
    worker = root / "src" / "worker.mrt"
    worker.write_text('''module worker
pub fn convert<T>(value: T) -> i32 {
    return value;
}''')
    assert project_cli_main(["check", str(root)]) == 1
    error = capsys.readouterr().err
    assert "error[M3002]: return type i64 does not match i32" in error
    assert f" --> {worker}:3:5" in error
    assert "note: generic instantiated here" in error
    assert f" --> {main_source}:4:12" in error


@pytest.mark.parametrize(
    ("source", "code", "line"),
    [
        (
            "module duplicate\nfn main() -> i32 { return 0; }\nfn main() -> i32 { return 1; }",
            "M0002",
            3,
        ),
        (
            "module field_type\nstruct Broken {\n    value: Missing;\n}\nfn main() -> i32 { return 0; }",
            "M3000",
            3,
        ),
        (
            "module trait_methods\ntrait Broken {\n    fn show(value: Self) -> i32;\n    fn show(value: Self) -> i32;\n}\nfn main() -> i32 { return 0; }",
            "M7101",
            4,
        ),
        (
            "module function_caps\nfn main() -> i32 requires_caps [missing] {\n    return 0;\n}",
            "M2001",
            2,
        ),
    ],
)
def test_declaration_errors_carry_precise_source_spans(source, code, line):
    error = semantic_error(source, "declaration_error.mrt")
    assert error.code == code
    assert (error.span.line, error.span.source_name) == (line, "declaration_error.mrt")
    rendered = render_exception(error, Path("declaration_error.mrt"), source)
    assert f" --> declaration_error.mrt:{line}:" in rendered


@pytest.mark.parametrize(
    ("source", "code", "line", "column", "excerpt"),
    [
        (
            "module generic_arity\nstruct Pair<T, U> { first: T; second: U; }\nfn main() -> i32 {\n    let pair: Pair<i64> = Pair<i64> { first: 1 };\n    return 0;\n}",
            "M7001",
            4,
            15,
            "Pair<i64>",
        ),
        (
            "module generic_bound\nfn identity<T: Copy>(value: T) -> T { return value; }\nfn main() -> i32 {\n    return identity<Buffer>(0);\n}",
            "M7002",
            4,
            12,
            "identity<Buffer>(0)",
        ),
    ],
)
def test_generic_expansion_errors_point_to_instantiation(source, code, line, column, excerpt):
    error = semantic_error(source, "generic_expansion.mrt")
    assert error.code == code
    assert (error.span.line, error.span.column, error.span.source_name) == (line, column, "generic_expansion.mrt")
    rendered = render_exception(error, Path("generic_expansion.mrt"), source)
    assert f" --> generic_expansion.mrt:{line}:{column}" in rendered
    assert excerpt in rendered
    assert "^^^^^^^^" in rendered


def test_project_generic_bound_error_points_to_calling_unit(tmp_path, capsys):
    root = tmp_path / "generic_bound_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="generic_bound_project"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n'
    )
    main_source = root / "src" / "main.mrt"
    main_source.write_text('''module generic_bound_project
import worker;
fn main() -> i32 {
    return identity<Buffer>(0);
}''')
    (root / "src" / "worker.mrt").write_text('''module worker
pub fn identity<T: Copy>(value: T) -> T { return value; }''')
    assert project_cli_main(["check", str(root)]) == 1
    error = capsys.readouterr().err
    assert "error[M7002]: type Buffer does not satisfy generic bound Copy" in error
    assert f" --> {main_source}:4:12" in error
    assert "4 |     return identity<Buffer>(0);" in error


def test_structured_diagnostic_payload_includes_related_source_note():
    error = move_error()
    payload = diagnostic_from_exception(error, Path("move_origin.mrt"), MOVE_SOURCE).to_dict()
    assert payload["severity"] == "error"
    assert payload["code"] == "M5001"
    assert payload["line"] == 8
    assert payload["notes"][0]["message"] == "value moved here (initializing destination)"
    assert payload["notes"][0]["line"] == 7


def test_compiler_cli_emits_json_diagnostics(tmp_path, capsys):
    source = tmp_path / "json_diagnostic.mrt"
    source.write_text('''module json_diagnostic
fn main()->i32 { return missing; }''')
    assert compiler_main(["check", str(source), "--diagnostic-format", "json"]) == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == "M3003"
    assert payload["path"] == str(source)
    assert payload["line"] == 2


def test_project_cli_emits_json_diagnostics(tmp_path, capsys):
    root = tmp_path / "json_project_diagnostic"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="json_project_diagnostic"\nentry="src/main.mrt"\nsources=["src/*.mrt"]\n'
    )
    source = root / "src" / "main.mrt"
    source.write_text('''module json_project_diagnostic
capability allocate;
fn main()->i32 { let allocator:Allocator=system_allocator(); let data:Buffer=buffer_new(allocator,8); drop(data); return 0; }''')
    assert project_cli_main(["check", str(root), "--diagnostic-format", "json"]) == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == "M2003"
    assert payload["path"] == str(source)
    assert payload["line"] == 3
