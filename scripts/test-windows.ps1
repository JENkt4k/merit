[CmdletBinding()]
param(
    [switch]$StopOnFirstFailure,
    [switch]$SkipActivation
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepositoryRoot

if (-not $SkipActivation) {
    & (Join-Path $PSScriptRoot "activate-windows-dev.ps1")
}

$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$MeritProject = Join-Path $RepositoryRoot ".venv\Scripts\merit-project.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtual environment is missing at $Python"
}
if (-not (Test-Path $MeritProject)) {
    throw "Merit is not installed in the virtual environment. Run: python -m pip install -e '.[dev]'"
}

$PytestArguments = @("-m", "pytest", "-q")
if ($StopOnFirstFailure) {
    $PytestArguments += "-x"
}

Write-Host ""
Write-Host "== pytest =="
& $Python @PytestArguments
if ($LASTEXITCODE -ne 0) {
    throw "pytest failed with exit code $LASTEXITCODE"
}

$Projects = @(
    @{ Name = "text_pipeline"; Path = "examples/projects/text_pipeline" },
    @{ Name = "binary_packet"; Path = "examples/projects/binary_packet" },
    @{ Name = "generic_result"; Path = "examples/projects/generic_result" },
    @{ Name = "trait_bounds"; Path = "examples/projects/trait_bounds" },
    @{ Name = "generic_collections"; Path = "examples/projects/generic_collections" },
    @{ Name = "borrowed_views"; Path = "examples/projects/borrowed_views" },
    @{ Name = "bootstrap_lexer"; Path = "examples/projects/bootstrap_lexer" },
    @{ Name = "cobol_finance_modernization"; Path = "examples/projects/cobol_finance_modernization" }
)

foreach ($Project in $Projects) {
    Write-Host ""
    Write-Host "== acceptance: $($Project.Name) =="
    & $MeritProject verify $Project.Path
    if ($LASTEXITCODE -ne 0) {
        throw "Acceptance project $($Project.Name) failed with exit code $LASTEXITCODE"
    }
}

$ScratchRoot = Join-Path $env:TEMP ("merit-gate-" + [Guid]::NewGuid().ToString("N"))
$FilesystemScratch = Join-Path $ScratchRoot "filesystem"
$LedgerScratch = Join-Path $ScratchRoot "ledger"
New-Item -ItemType Directory -Force $FilesystemScratch, $LedgerScratch | Out-Null

try {
    Write-Host ""
    Write-Host "== acceptance: filesystem_capabilities =="
    Push-Location $FilesystemScratch
    try {
        & $MeritProject verify (Join-Path $RepositoryRoot "examples/projects/filesystem_capabilities") -o (Join-Path $FilesystemScratch "filesystem_capabilities")
        if ($LASTEXITCODE -ne 0) {
            throw "filesystem_capabilities failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "== acceptance: ledger_app =="
    Push-Location $LedgerScratch
    try {
        & $MeritProject verify (Join-Path $RepositoryRoot "examples/projects/ledger_app") -o (Join-Path $LedgerScratch "ledger_app")
        if ($LASTEXITCODE -ne 0) {
            throw "ledger_app failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item -Recurse -Force $ScratchRoot -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Merit Windows local gate passed: pytest and 10/10 acceptance projects verified."
