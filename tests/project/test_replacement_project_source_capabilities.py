from __future__ import annotations

from pathlib import Path

from merit.project.loader import load_project
from merit.project.replacement_source import canonical_replacement_project_source


def test_project_envelope_blanks_cross_module_duplicate_capabilities(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source_root = root / "src"
    source_root.mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="capability_project"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n',
        encoding="utf-8",
    )
    (source_root / "helper.mrt").write_text(
        "module helper\n"
        "capability allocate;\n"
        "pub fn helper() -> i32 { return 1; }\n",
        encoding="utf-8",
    )
    (source_root / "main.mrt").write_text(
        "module main\n"
        "import helper;\n"
        "capability allocate;\n"
        "fn main() -> i32 { return helper(); }\n",
        encoding="utf-8",
    )

    project = load_project(root / "Merit.toml")
    envelope = canonical_replacement_project_source(project)

    # The declarations are valid in their original module scopes. Flattening
    # must not manufacture a duplicate declaration for the native frontend.
    assert envelope.count("capability allocate;") == 1
    assert "pub fn helper()" in envelope
    assert "fn main()" in envelope


def test_project_envelope_desugars_legacy_i64vec_surface(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source_root = root / "src"
    source_root.mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="legacy_vector_project"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n',
        encoding="utf-8",
    )
    (source_root / "main.mrt").write_text(
        "module main\n"
        "capability allocate;\n"
        "fn main() -> i32 { with capability allocate { "
        "let a: Allocator = system_allocator(); "
        "var v: I64Vec = i64vec_new(a, 1); "
        "i64vec_push(v, 7); "
        "print(i64vec_len(v)); print(i64vec_get(v, 0)); "
        "drop(v); } return 0; }\n",
        encoding="utf-8",
    )

    project = load_project(root / "Merit.toml")
    envelope = canonical_replacement_project_source(project)

    assert "I64Vec" not in envelope
    assert "i64vec_" not in envelope
    assert "Vec<i64>" in envelope
    assert "vec_new<i64>" in envelope
    assert "vec_push<i64>" in envelope
    assert "vec_len<i64>" in envelope
    assert "vec_get<i64>" in envelope
    assert "drop(v)" not in envelope
    assert "vec_drop<i64>(v)" in envelope
