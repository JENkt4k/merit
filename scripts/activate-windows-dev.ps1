[CmdletBinding()]
param(
    [string]$Msys2Root = $env:MSYS2_ROOT,
    [string]$TempRoot = "C:\Temp\merit-gcc\tmp"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvScripts = Join-Path $RepositoryRoot ".venv\Scripts"

if (-not (Test-Path $VenvScripts)) {
    throw "Merit virtual environment not found at $VenvScripts. Run: py -3.11 -m venv .venv"
}

if (-not $Msys2Root) {
    $Msys2Root = @("C:\msys64", "D:\msys64") |
        Where-Object { Test-Path (Join-Path $_ "ucrt64\bin\gcc.exe") } |
        Select-Object -First 1
}

if (-not $Msys2Root) {
    throw "MSYS2 UCRT64 GCC was not found. Set MSYS2_ROOT or install MSYS2 under C:\msys64 or D:\msys64."
}

$Msys2Root = (Resolve-Path $Msys2Root).Path
$UcrtBin = Join-Path $Msys2Root "ucrt64\bin"
$UsrBin = Join-Path $Msys2Root "usr\bin"
$Compiler = Join-Path $UcrtBin "gcc.exe"

if (-not (Test-Path $Compiler)) {
    throw "MSYS2 UCRT64 GCC was not found at $Compiler"
}

New-Item -ItemType Directory -Force $TempRoot | Out-Null

$ExistingPath = $env:PATH -split ";" | Where-Object {
    $_ -and
    $_ -ine $VenvScripts -and
    $_ -ine $UcrtBin -and
    $_ -ine $UsrBin
}
$env:PATH = (@($VenvScripts, $UcrtBin, $UsrBin) + $ExistingPath) -join ";"

$env:MSYS2_ROOT = $Msys2Root
$env:MSYSTEM = "UCRT64"
$env:MINGW_PREFIX = "/ucrt64"
$env:MSYSTEM_PREFIX = "/ucrt64"
$env:CHERE_INVOKING = "1"
$env:CC = $Compiler
$env:TEMP = $TempRoot
$env:TMP = $TempRoot

@(
    "GCC_EXEC_PREFIX",
    "COMPILER_PATH",
    "LIBRARY_PATH",
    "CPATH",
    "C_INCLUDE_PATH",
    "CPLUS_INCLUDE_PATH"
) | ForEach-Object {
    Remove-Item "Env:$_" -ErrorAction SilentlyContinue
}

$Python = Join-Path $VenvScripts "python.exe"
if (-not (Test-Path $Python)) {
    throw "Python was not found at $Python"
}

Write-Host "Merit Windows development environment ready"
Write-Host "  Repository: $RepositoryRoot"
Write-Host "  Python:     $Python"
Write-Host "  Compiler:   $Compiler"
Write-Host "  MSYSTEM:    $env:MSYSTEM"
Write-Host "  Temp:       $TempRoot"
Write-Host ""
Write-Host "Validate the environment:"
Write-Host "  .\.venv\Scripts\python.exe .\scripts\doctor.py"
Write-Host "Run a fast development gate:"
Write-Host "  .\scripts\test-windows.ps1 -Gate fast"
Write-Host "Run the authoritative Windows full gate:"
Write-Host "  .\scripts\test-windows.ps1 -Gate full"
