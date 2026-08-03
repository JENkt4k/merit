from pathlib import Path

import pytest

from merit.compiler import Checker, CompileError, mir, parse
from merit.diagnostics import render_exception
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
    assert all(span.source_name for span in spans)
