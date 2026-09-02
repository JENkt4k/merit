from __future__ import annotations

from pathlib import Path

from merit.project.loader import load_project


def test_project_loading_uses_explicit_utf8_when_host_default_is_cp1252(
    tmp_path: Path, monkeypatch,
) -> None:
    root = tmp_path / "utf8_project"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname = "utf8_project"\nentry = "src/main.mrt"\n'
        'sources = ["src/**/*.mrt"]\n',
        encoding="utf-8",
    )
    (root / "src" / "main.mrt").write_text(
        'module main\nfn main()->i32 { let text:String="Aé"; print(text); return 0; }\n',
        encoding="utf-8",
    )

    original_read_text = Path.read_text

    def cp1252_default(self: Path, *args, **kwargs):
        if args:
            if args[0] is None:
                args = ("cp1252", *args[1:])
        elif kwargs.get("encoding") is None:
            kwargs["encoding"] = "cp1252"
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", cp1252_default)

    project = load_project(root / "Merit.toml")

    assert '"Aé"' in project.units[0].parser_source
    assert "AÃ©" not in project.units[0].parser_source
