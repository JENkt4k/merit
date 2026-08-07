from __future__ import annotations

from pathlib import Path

import pytest

from merit.project.loader import ProjectError, load_project


def _write_project(root: Path, source: str) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "visibility_vec"\nentry = "src/main.mrt"\nsources = ["src/*.mrt"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(source, encoding="utf-8")
    return root / "Merit.toml"


def test_public_function_may_expose_vec_of_public_type(tmp_path):
    manifest = _write_project(
        tmp_path / "public_vec",
        "module visibility_vec\n"
        "pub struct Item { value:i32; }\n"
        "pub fn count(borrow items:Vec<Item>)->i64 { return vec_len<Item>(items); }\n"
        "fn main()->i32 { return 0; }\n",
    )

    project = load_project(manifest)

    assert "Item" in project.program.exports
    assert "count" in project.program.exports


def test_public_function_may_return_vec_of_public_type(tmp_path):
    manifest = _write_project(
        tmp_path / "public_vec_return",
        "module visibility_vec\n"
        "capability allocate;\n"
        "pub struct Item { value:i32; }\n"
        "pub fn empty(allocator:Allocator)->Vec<Item> requires_caps [allocate] {\n"
        "    return vec_new<Item>(allocator,0);\n"
        "}\n"
        "fn main()->i32 { return 0; }\n",
    )

    project = load_project(manifest)

    assert "empty" in project.program.exports


def test_public_function_may_expose_nested_vec_of_public_type(tmp_path):
    manifest = _write_project(
        tmp_path / "public_nested_vec",
        "module visibility_vec\n"
        "pub struct Item { value:i32; }\n"
        "pub fn count_nested(borrow items:Vec<Vec<Item>>)->i64 { return 0; }\n"
        "fn main()->i32 { return 0; }\n",
    )

    project = load_project(manifest)

    assert "count_nested" in project.program.exports


def test_public_function_cannot_hide_private_type_inside_vec(tmp_path):
    manifest = _write_project(
        tmp_path / "private_vec",
        "module visibility_vec\n"
        "struct Secret { value:i32; }\n"
        "pub fn count(borrow secrets:Vec<Secret>)->i64 { return vec_len<Secret>(secrets); }\n"
        "fn main()->i32 { return 0; }\n",
    )

    with pytest.raises(
        ProjectError,
        match=r"public function count exposes private type Vec__Secret",
    ):
        load_project(manifest)


def test_public_function_cannot_return_vec_of_private_type(tmp_path):
    manifest = _write_project(
        tmp_path / "private_vec_return",
        "module visibility_vec\n"
        "capability allocate;\n"
        "struct Secret { value:i32; }\n"
        "pub fn empty(allocator:Allocator)->Vec<Secret> requires_caps [allocate] {\n"
        "    return vec_new<Secret>(allocator,0);\n"
        "}\n"
        "fn main()->i32 { return 0; }\n",
    )

    with pytest.raises(
        ProjectError,
        match=r"public function empty exposes private type Vec__Secret",
    ):
        load_project(manifest)


def test_nested_vec_cannot_launder_private_element_visibility(tmp_path):
    manifest = _write_project(
        tmp_path / "private_nested_vec",
        "module visibility_vec\n"
        "struct Secret { value:i32; }\n"
        "pub fn count_nested(borrow secrets:Vec<Vec<Secret>>)->i64 { return 0; }\n"
        "fn main()->i32 { return 0; }\n",
    )

    with pytest.raises(
        ProjectError,
        match=r"public function count_nested exposes private type Vec__Vec__Secret",
    ):
        load_project(manifest)
