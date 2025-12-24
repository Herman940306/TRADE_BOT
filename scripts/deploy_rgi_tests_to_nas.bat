@echo off
REM ============================================================================
REM Project Autonomous Alpha v1.5.0
REM RGI Test Suite - Deploy to NAS from Windows
REM ============================================================================
REM
REM Reliability Level: SOVEREIGN TIER (Mission-Critical)
REM Purpose: Sync project files to NAS and run RGI tests
REM
REM USAGE:
REM   scripts\deploy_rgi_tests_to_nas.bat
REM
REM PREREQUISITES:
REM   - OpenSSH client installed (Windows 10+ has it built-in)
REM   - SSH key configured OR password authentication enabled
REM   - NAS accessible at configured IP
REM
REM ============================================================================

setlocal enabledelayedexpansion

echo ============================================
echo RGI Test Suite - NAS Deployment
echo Project Autonomous Alpha v1.5.0
echo ============================================
echo.

REM Configuration
set NAS_USER=Wolf
set NAS_IP=NAS
set NAS_PATH=/volume2/docker/Herman/Trade_Bot
set LOCAL_PATH=%~dp0..

echo [CONFIG] NAS Target: %NAS_USER%@%NAS_IP%:%NAS_PATH%
echo [CONFIG] Local Path: %LOCAL_PATH%
echo.

REM Step 1: Create remote directory if needed
echo [1/4] Ensuring remote directory exists...
ssh %NAS_USER%@%NAS_IP% "mkdir -p %NAS_PATH%"
if errorlevel 1 (
    echo [FAIL] Could not connect to NAS or create directory
    echo        Check SSH connectivity: ssh %NAS_USER%@%NAS_IP%
    exit /b 1
)
echo [OK] Remote directory ready
echo.

REM Step 2: Sync project files using SCP
echo [2/4] Syncing project files to NAS...
echo        This may take a few minutes...

REM Sync core directories
scp -r "%LOCAL_PATH%\app" %NAS_USER%@%NAS_IP%:%NAS_PATH%/
scp -r "%LOCAL_PATH%\tests" %NAS_USER%@%NAS_IP%:%NAS_PATH%/
scp -r "%LOCAL_PATH%\database" %NAS_USER%@%NAS_IP%:%NAS_PATH%/
scp -r "%LOCAL_PATH%\jobs" %NAS_USER%@%NAS_IP%:%NAS_PATH%/
scp -r "%LOCAL_PATH%\scripts" %NAS_USER%@%NAS_IP%:%NAS_PATH%/

REM Sync deployment files
scp "%LOCAL_PATH%\docker-compose.test.yml" %NAS_USER%@%NAS_IP%:%NAS_PATH%/
scp "%LOCAL_PATH%\Dockerfile.test" %NAS_USER%@%NAS_IP%:%NAS_PATH%/
scp "%LOCAL_PATH%\requirements.txt" %NAS_USER%@%NAS_IP%:%NAS_PATH%/

if errorlevel 1 (
    echo [FAIL] SCP transfer failed
    exit /b 1
)
echo [OK] Files synced to NAS
echo.

REM Step 3: Set permissions on NAS
echo [3/4] Setting execute permissions...
ssh %NAS_USER%@%NAS_IP% "chmod +x %NAS_PATH%/scripts/*.sh %NAS_PATH%/scripts/*.py"
echo [OK] Permissions set
echo.

REM Step 4: Run tests on NAS
echo [4/4] Running RGI test suite on NAS...
echo ============================================
ssh %NAS_USER%@%NAS_IP% "cd %NAS_PATH% && docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit"

echo.
echo ============================================
echo Deployment complete. Check output above for test results.
echo ============================================

endlocal
