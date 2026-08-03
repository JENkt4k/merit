from pathlib import Path

import pytest

from merit.compiler import Checker, CompileError, main as compiler_main, mir, parse
from merit.diagnostics import render_exception
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


def test_project_merge_retains_source_identity_for_semantic_nodes():
    project = load_project(Path("examples/projects/binary_packet/Merit.toml"))
    spans = list(project.program.spans.values())
    assert spans
    source_names = {span.source_name for span in spans}
    assert str((Path("examples/projects/binary_packet/src/main.mrt")).resolve()) in source_names
    assert str((Path("examples/projects/binary_packet/src/packet.mrt")).resolve()) in source_names


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
