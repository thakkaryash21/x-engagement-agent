$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$patterns = @(
    "D:\\cruitical-kb",
    "claude-code-workflows/twitter-agent",
    "\.claude/writing",
    "03-traction/metrics.md",
    "localhost:9222"
)

$failed = $false
foreach ($pattern in $patterns) {
    $hits = rg -n $pattern $repoRoot -g '!data/**' -g '!.git/**' -g '!scripts/check-sensitive-data.ps1'
    if ($LASTEXITCODE -eq 0) {
        $failed = $true
        Write-Host "Pattern found: $pattern"
        Write-Host $hits
    }
}

if ($failed) { exit 1 }
Write-Host "No sensitive source-path references found outside data/."
