# ============================================================================
# Project Autonomous Alpha v1.3.2
# Smoke Test Runner (PowerShell)
# ============================================================================

Write-Host "=============================================="
Write-Host "SOVEREIGN SMOKE TEST: Immutability Verification"
Write-Host "=============================================="
Write-Host ""

# Check if Docker is running
$dockerRunning = docker info 2>$null
if (-not $dockerRunning) {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if container is running
$containerRunning = docker ps --filter "name=autonomous_alpha_db" --format "{{.Names}}"
if (-not $containerRunning) {
    Write-Host "[INFO] Starting PostgreSQL container..." -ForegroundColor Yellow
    docker-compose up -d
    Write-Host "[INFO] Waiting for PostgreSQL to be ready..."
    Start-Sleep -Seconds 10
}

Write-Host "[INFO] Running smoke tests..." -ForegroundColor Cyan
Write-Host ""

# Run the smoke test
docker exec -i autonomous_alpha_db psql -U sovereign -d autonomous_alpha -f /docker-entrypoint-initdb.d/../tests/smoke_test_immutability.sql

Write-Host ""
Write-Host "=============================================="
Write-Host "Smoke test execution complete."
Write-Host "=============================================="
