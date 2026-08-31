from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MINIMUM_PYTHON = (3, 11)


def _version_line(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (completed.stdout or "").strip().splitlines()
    return output[0] if output else None


def _find_c_compiler() -> tuple[str | None, str | None]:
    configured = os.environ.get("CC")
    candidates = [configured] if configured else []
    candidates.extend(["cc", "gcc", "clang", "cl"])
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        resolved = shutil.which(candidate)
        if resolved:
            line = _version_line([resolved, "--version"])
            if line is None and Path(resolved).name.lower() in {"cl", "cl.exe"}:
                line = _version_line([resolved])
            return resolved, line
    return None, None


def _print_check(name: str, value: str, ok: bool, *, required: bool = True) -> None:
    if ok:
        status = "PASS"
    elif required:
        status = "FAIL"
    else:
        status = "OPTIONAL"
    print(f"{name:<22} {value:<56} {status}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Merit development toolchain.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="also require Java and .NET runtimes used by full benchmark/parity validation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Merit development environment")
    print(f"repository: {REPOSITORY_ROOT}")
    print()

    ok = True

    python_version = platform.python_version()
    python_ok = sys.version_info >= MINIMUM_PYTHON
    _print_check("Python", python_version, python_ok)
    ok &= python_ok

    _print_check("Platform", f"{platform.system()} {platform.machine()}", True)

    pip_line = _version_line([sys.executable, "-m", "pip", "--version"])
    pip_ok = pip_line is not None
    _print_check("pip", pip_line or "not available", pip_ok)
    ok &= pip_ok

    pytest_line = _version_line([sys.executable, "-m", "pytest", "--version"])
    pytest_ok = pytest_line is not None
    _print_check("pytest", pytest_line or "not installed", pytest_ok)
    ok &= pytest_ok

    compiler, compiler_version = _find_c_compiler()
    compiler_ok = compiler is not None
    compiler_text = compiler or "not found (set CC or install GCC/Clang/MSVC)"
    if compiler_version:
        compiler_text = f"{compiler_text} [{compiler_version}]"
    _print_check("C compiler", compiler_text, compiler_ok)
    ok &= compiler_ok

    git = shutil.which("git")
    _print_check("Git", git or "not found", git is not None)
    ok &= git is not None

    java = shutil.which("java")
    java_line = _version_line([java, "-version"]) if java else None
    _print_check("Java", java_line or java or "not found", java is not None, required=args.full)
    if args.full:
        ok &= java is not None

    dotnet = shutil.which("dotnet")
    dotnet_line = _version_line([dotnet, "--version"]) if dotnet else None
    _print_check(".NET", dotnet_line or dotnet or "not found", dotnet is not None, required=args.full)
    if args.full:
        ok &= dotnet is not None

    merit_package = REPOSITORY_ROOT / "merit"
    package_ok = merit_package.is_dir()
    _print_check("Merit package", str(merit_package), package_ok)
    ok &= package_ok

    if pip_ok:
        pip_check = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            cwd=REPOSITORY_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        dependency_ok = pip_check.returncode == 0
        dependency_text = (pip_check.stdout or "").strip().splitlines()
        _print_check(
            "Dependency check",
            dependency_text[-1] if dependency_text else "pip check completed",
            dependency_ok,
        )
        ok &= dependency_ok

    print()
    if ok:
        print("Environment ready.")
        print("Next: python scripts/gate.py fast")
        return 0

    print("Environment is not ready. Fix the FAIL entries and rerun this command.")
    if os.name == "nt" and compiler is None:
        print("Windows recommendation: install MSYS2 UCRT64 GCC and set CC=gcc, or use a Developer Command Prompt for MSVC.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
