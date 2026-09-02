[CmdletBinding()]
param(
    [ValidateSet("smoke", "fast", "subsystem", "acceptance", "full")]
    [string]$Gate = "full",
    [switch]$StopOnFirstFailure,
    [switch]$SkipActivation,
    [int]$Durations = 0,
    [string]$Msys2Root = $env:MSYS2_ROOT
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepositoryRoot

# Merit source and native program text are UTF-8. Force Python's text-mode
# defaults to the same deterministic encoding even when activation is skipped.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (-not $SkipActivation) {
    if ($Msys2Root) {
        & (Join-Path $PSScriptRoot "activate-windows-dev.ps1") -Msys2Root $Msys2Root
    }
    else {
        & (Join-Path $PSScriptRoot "activate-windows-dev.ps1")
    }
}

$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python virtual environment is missing at $Python"
}

$DoctorArguments = @((Join-Path $PSScriptRoot "doctor.py"))
if ($Gate -eq "full") {
    $DoctorArguments += "--full"
}
& $Python @DoctorArguments
if ($LASTEXITCODE -ne 0) {
    throw "Merit environment doctor failed with exit code $LASTEXITCODE"
}

$GateArguments = @((Join-Path $PSScriptRoot "gate.py"), $Gate)
if ($StopOnFirstFailure) {
    $GateArguments += "--fail-fast"
}
if ($Durations -gt 0) {
    $GateArguments += @("--durations", $Durations.ToString())
}

& $Python @GateArguments
if ($LASTEXITCODE -ne 0) {
    throw "Merit $Gate gate failed with exit code $LASTEXITCODE"
}