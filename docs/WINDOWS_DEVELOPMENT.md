# Windows development

Merit can be developed and tested from native Windows PowerShell with Python 3.11 and MSYS2 UCRT64 GCC.

## Prerequisites

Install:

- Python 3.11
- Git
- MSYS2
- the MSYS2 UCRT64 GCC toolchain

From the **MSYS2 UCRT64** shell:

```bash
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-binutils
```

The default supported MSYS2 roots are:

- `C:\msys64`
- `D:\msys64`

Set `MSYS2_ROOT` before activation when using another location.

## Create the Python environment

From PowerShell in the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

The `wheel` package is required when editable installation is performed without build isolation.

## Activate the native toolchain

```powershell
.\scripts\activate-windows-dev.ps1
```

The script:

- locates MSYS2 UCRT64 GCC;
- places the virtual environment and UCRT64 tools first on `PATH`;
- sets `MSYSTEM=UCRT64` and related MSYS2 variables;
- removes environment variables that can redirect GCC internals;
- assigns a controlled compiler temporary directory;
- sets `CC` to the selected UCRT64 `gcc.exe`.

For a nonstandard MSYS2 installation:

```powershell
.\scripts\activate-windows-dev.ps1 -Msys2Root "E:\tools\msys64"
```

## Run the complete local gate

```powershell
.\scripts\test-windows.ps1
```

This runs:

1. the complete pytest suite;
2. all nine interpreter/native acceptance projects;
3. filesystem and ledger acceptance projects inside isolated temporary directories.

Stop at the first pytest failure with:

```powershell
.\scripts\test-windows.ps1 -StopOnFirstFailure
```

When the environment is already active:

```powershell
.\scripts\test-windows.ps1 -SkipActivation
```

## Testing a pull-request branch while GitHub Actions is unavailable

Preserve any local work first:

```powershell
git status
git stash push -u -m "temporary local work"
```

Fetch and switch to the PR branch:

```powershell
git fetch origin
git switch fix/windows-native-build-diagnostics
git pull --ff-only
```

Reinstall only when `pyproject.toml` or package entry points changed:

```powershell
python -m pip install -e ".[dev]"
```

Then run:

```powershell
.\scripts\test-windows.ps1
```

Return to `main` afterward:

```powershell
git switch main
git pull --ff-only
```

Restore stashed work when appropriate:

```powershell
git stash list
git stash pop
```

## Diagnosing native compiler failures

Merit reports:

- the exact compiler or linker command;
- the exit code;
- captured stdout and stderr;
- paths to generated C, headers, objects, libraries, and executables.

A minimal compiler check is:

```powershell
@'
int main(void) { return 0; }
'@ | Set-Content -Encoding ascii "$env:TEMP\merit-hello.c"

& $env:CC -v -c "$env:TEMP\merit-hello.c" -o "$env:TEMP\merit-hello.o"
$LASTEXITCODE
```

If this fails before testing Merit source, validate the same command in the MSYS2 UCRT64 shell and compare the inherited environment.

## Known portability rule for generated test source

Do not embed `WindowsPath` values directly inside Merit string literals because backslashes are escape characters. Generate a language string literal with JSON escaping or use a forward-slash path:

```python
import json

literal = json.dumps(str(path))
portable = path.as_posix()
```

## Supported boundary

The Windows path currently targets native Python plus MSYS2 UCRT64 GCC. MSVC support is not yet part of the alpha toolchain contract.
