param(
    [string]$DataRoot = "data"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot $DataRoot
$source = Join-Path $repoRoot "example\data"

if (Test-Path -LiteralPath $target) {
    Write-Error "Data root already exists: $target. Refusing to overwrite private runtime data."
}

Copy-Item -LiteralPath $source -Destination $target -Recurse
Write-Host "Initialized private data root at $target"
