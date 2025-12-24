# ============================================================================
# Project Autonomous Alpha v1.5.0
# Sync Files to NAS (No Docker execution)
# ============================================================================
#
# USAGE:
#   .\scripts\Sync-ToNas.ps1
#
# Then SSH to NAS and run:
#   cd /volume2/docker/Herman/Trade_Bot
#   docker compose -f docker-compose.test.yml up --build
#
# ============================================================================

param(
    [string]$NasUser = "Wolf",
    [string]$NasIp = "NAS",
    [string]$NasPath = "/volume2/docker/Herman/Trade_Bot"
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Sync to NAS - Project Autonomous Alpha" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$LocalPath = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "[1/3] Creating remote directory..." -ForegroundColor White
ssh "$NasUser@$NasIp" "mkdir -p $NasPath/test_results"

Write-Host "[2/3] Syncing files (using SCP legacy mode)..." -ForegroundColor White

# Directories
$directories = @("app", "tests", "database", "jobs", "scripts", "services", "tools")
foreach ($dir in $directories) {
    Write-Host "       $dir/..." -ForegroundColor Gray
    scp -O -r "$LocalPath\$dir" "${NasUser}@${NasIp}:${NasPath}/"
}

# Files
$files = @("docker-compose.test.yml", "Dockerfile.test", "requirements.txt")
foreach ($file in $files) {
    Write-Host "       $file..." -ForegroundColor Gray
    scp -O "$LocalPath\$file" "${NasUser}@${NasIp}:${NasPath}/"
}

Write-Host "[3/3] Setting permissions..." -ForegroundColor White
ssh "$NasUser@$NasIp" "chmod +x $NasPath/scripts/*.sh $NasPath/scripts/*.py 2>/dev/null || true"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "SYNC COMPLETE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Now SSH to NAS and run:" -ForegroundColor Yellow
Write-Host "  ssh Wolf@NAS" -ForegroundColor White
Write-Host "  cd /volume2/docker/Herman/Trade_Bot" -ForegroundColor White
Write-Host "  docker compose -f docker-compose.test.yml up --build" -ForegroundColor White
Write-Host ""
