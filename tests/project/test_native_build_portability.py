from __future__ import annotations

from pathlib import Path
import os
import subprocess

import pytest

from merit.project.build import (
    NativeBuildError,
    _native_environment,
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

    assert isinstance(raised.value, subprocess.CalledProcessError)
    assert raised.value.returncode == 1
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


def test_native_environment_uses_controlled_temp_directory(tmp_path):
    environment = _native_environment(tmp_path)
    assert environment["TEMP"] == str(tmp_path)
    assert environment["TMP"] == str(tmp_path)
    assert tmp_path.is_dir()


def test_native_environment_preserves_host_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MERIT_SENTINEL", "present")
    environment = _native_environment(tmp_path)
    assert environment["MERIT_SENTINEL"] == "present"


@pytest.mark.skipif(os.name != "nt", reason="MSYS2 UCRT64 environment is Windows-specific")
def test_native_environment_configures_msys2_ucrt64(monkeypatch, tmp_path):
    root = tmp_path / "msys64"
    gcc = root / "ucrt64" / "bin" / "gcc.exe"
    gcc.parent.mkdir(parents=True)
    gcc.write_bytes(b"")
    (root / "usr" / "bin").mkdir(parents=True)

    monkeypatch.setenv("MSYS2_ROOT", str(root))
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    monkeypatch.setenv("GCC_EXEC_PREFIX", "bad")
    monkeypatch.setenv("CPATH", "bad")

    environment = _native_environment(tmp_path / "temp")

    assert environment["MSYSTEM"] == "UCRT64"
    assert environment["MINGW_PREFIX"] == "/ucrt64"
    assert environment["MSYSTEM_PREFIX"] == "/ucrt64"
    assert environment["CHERE_INVOKING"] == "1"
    assert environment["PATH"].split(os.pathsep)[:2] == [
        str(root / "ucrt64" / "bin"),
        str(root / "usr" / "bin"),
    ]
    assert "GCC_EXEC_PREFIX" not in environment
    assert "CPATH" not in environment
