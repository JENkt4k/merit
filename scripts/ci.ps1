[CmdletBinding()]
param(
    [ValidateSet("smoke", "fast", "subsystem", "acceptance", "full")]
    [string]$Gate = "full",
    [switch]$StopOnFirstFailure,
    [int]$Durations = 0
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepositoryRoot

$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$DoctorArguments = @((Join-Path $PSScriptRoot "doctor.py"))
if ($Gate -eq "full") {
    $DoctorArguments += "--full"
}
& $Python @DoctorArguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$Arguments = @((Join-Path $PSScriptRoot "gate.py"), $Gate)
if ($StopOnFirstFailure) {
    $Arguments += "--fail-fast"
}
if ($Durations -gt 0) {
    $Arguments += @("--durations", $Durations.ToString())
}

& $Python @Arguments
exit $LASTEXITCODE
