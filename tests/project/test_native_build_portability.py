from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from merit.project.build import (
    NativeBuildError,
    _native_executable_path,
    _run_native_command,
    _temporary_object_path,
)


def test_windows_executable_path_adds_exe_suffix():
    assert _native_executable_path(Path("program"), "win32") == Path("program.exe")


def test_windows_executable_path_preserves_existing_exe_suffix():
    assert _native_executable_path(Path("program.exe"), "win32") == Path(
        "program.exe"
    )


def test_non_windows_executable_path_is_unchanged():
    assert _native_executable_path(Path("program"), "linux") == Path("program")


def test_temporary_object_path_is_not_precreated(tmp_path):
    object_path = tmp_path / "cached.o"
    temporary_path = _temporary_object_path(tmp_path, object_path)

    assert temporary_path.parent == tmp_path
    assert temporary_path.name.endswith(".tmp.o")
    assert not temporary_path.exists()


def test_native_command_reports_command_streams_and_artifacts(monkeypatch, tmp_path):
    source = tmp_path / "generated.c"
    source.write_text("int main(void) { return 0; }", encoding="utf-8")

    def fail(*args, **kwargs):
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="compiler stdout\n",
            stderr="generated.c:1: error: demonstration\n",
        )

    monkeypatch.setattr(subprocess, "run", fail)

    with pytest.raises(NativeBuildError) as raised:
        _run_native_command(
            ["cc", "-c", str(source)],
            phase="compilation",
            artifacts=(source,),
        )

    message = str(raised.value)
    assert "native compilation failed with exit code 1" in message
    assert "command:" in message
    assert "cc" in message
    assert str(source.resolve()) in message
    assert "compiler stdout" in message
    assert "generated.c:1: error: demonstration" in message


def test_native_command_returns_successful_process(monkeypatch):
    expected = subprocess.CompletedProcess(["cc"], 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: expected)

    assert _run_native_command(["cc"], phase="compilation") is expected
