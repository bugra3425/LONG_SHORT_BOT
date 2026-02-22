#!/usr/bin/env pwsh
# Git Hooks Installer for Windows (PowerShell)
# Usage: .\scripts\install-hooks.ps1

$ErrorActionPreference = "Stop"

Write-Host "Installing Git Hooks..." -ForegroundColor Cyan

# Get paths
$RepoRoot = Split-Path -Parent $PSScriptRoot
$HooksSource = Join-Path $RepoRoot ".git-hooks"
$GitDir = Join-Path $RepoRoot ".git"
$HooksTarget = Join-Path $GitDir "hooks"

# Check if .git exists
if (-not (Test-Path $HooksTarget)) {
    Write-Host "ERROR: .git directory not found" -ForegroundColor Red
    exit 1
}

# Copy hooks
$Hooks = @("commit-msg", "pre-commit")

foreach ($Hook in $Hooks) {
    $Source = Join-Path $HooksSource $Hook
    $Target = Join-Path $HooksTarget $Hook
    
    if (Test-Path $Source) {
        Copy-Item -Path $Source -Destination $Target -Force
        Write-Host "  Installed: $Hook" -ForegroundColor Green
    } else {
        Write-Host "  Not found: $Hook" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Git hooks installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Commit message format:" -ForegroundColor Cyan
Write-Host '  type(scope): subject' -ForegroundColor White
Write-Host ""
Write-Host "Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert" -ForegroundColor Gray
