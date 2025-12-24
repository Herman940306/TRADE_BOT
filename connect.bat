@echo off
REM ============================================================================
REM Project Autonomous Alpha - Secure Connection Bridge
REM Version: 1.4.0
REM Reliability Level: L6 Critical
REM ============================================================================
REM
REM PURPOSE: Establishes secure SSH/SSE connection to NAS infrastructure
REM          for multi-user monitoring access.
REM
REM PRIVACY: No credentials stored in this file. All authentication
REM          is handled via environment variables or user prompt.
REM
REM ============================================================================

setlocal enabledelayedexpansion

REM Configuration - Load from environment or use defaults
set "NAS_HOST=%SOVEREIGN_NAS_HOST%"
set "NAS_PORT=%SOVEREIGN_NAS_PORT%"
if "%NAS_HOST%"=="" set "NAS_HOST=nas.local"
if "%NAS_PORT%"=="" set "NAS_PORT=22"

REM Display banner
echo.
echo ============================================================================
echo   Project Autonomous Alpha - Sovereign Connection Bridge v1.4.0
echo ============================================================================
echo.
echo   Reliability Level: L6 Critical
echo   Transport: SSH/SSE Bridge
echo   Target: NAS Infrastructure
echo.
echo ============================================================================
echo.

REM Prompt for username
set /p "USERNAME=Enter your username: "

if "%USERNAME%"=="" (
    echo.
    echo [ERROR] Username cannot be empty.
    echo.
    echo Troubleshooting:
    echo   1. Ensure you have a valid NAS account
    echo   2. Contact system administrator for access
    echo.
    pause
    exit /b 1
)

REM Validate Python environment
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found in PATH.
    echo.
    echo Troubleshooting:
    echo   1. Install Python 3.8 or higher
    echo   2. Add Python to system PATH
    echo   3. Restart command prompt
    echo.
    pause
    exit /b 1
)

REM Check for required dependencies
python -c "import paramiko" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Required dependency 'paramiko' not installed.
    echo.
    echo Installing dependencies...
    pip install paramiko
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Display connection info
echo.
echo Connecting as: %USERNAME%
echo Target Host: %NAS_HOST%:%NAS_PORT%
echo.

REM Launch the Python bridge with session management
python -c "
import sys
import os
import uuid
import getpass

# Generate unique session ID
session_id = str(uuid.uuid4())[:8]
username = '%USERNAME%'

print(f'[SESSION] ID: {session_id}')
print(f'[SESSION] User: {username}')
print()

# Prompt for password securely
password = getpass.getpass('Enter password: ')

if not password:
    print('[ERROR] Password cannot be empty.')
    sys.exit(1)

# Set environment for bridge
os.environ['SOVEREIGN_SESSION_ID'] = session_id
os.environ['SOVEREIGN_USERNAME'] = username
os.environ['SOVEREIGN_PASSWORD'] = password

print()
print('[STATUS] Launching SSE Bridge...')
print('[STATUS] Press Ctrl+C to disconnect')
print()

# Import and run the bridge
try:
    from app.transport.session_manager import SessionManager
    
    manager = SessionManager()
    import asyncio
    asyncio.run(manager.start_session(
        username=username,
        session_id=session_id,
        host=os.environ.get('SOVEREIGN_NAS_HOST', 'nas.local'),
        port=int(os.environ.get('SOVEREIGN_NAS_PORT', '22'))
    ))
except ImportError:
    print('[WARN] Session manager not available, using legacy bridge')
    # Fallback to legacy bridge
    try:
        import sse_bridge
        sse_bridge.main()
    except Exception as e:
        print(f'[ERROR] Bridge failed: {e}')
        sys.exit(1)
except KeyboardInterrupt:
    print()
    print('[STATUS] Session terminated by user')
except Exception as e:
    print(f'[ERROR] Connection failed: {e}')
    print()
    print('Troubleshooting:')
    print('  1. Verify NAS is online and accessible')
    print('  2. Check username and password')
    print('  3. Ensure SSH service is running on NAS')
    print('  4. Check firewall settings')
    sys.exit(1)
"

if errorlevel 1 (
    echo.
    echo [ERROR] Connection failed. See above for details.
    echo.
    pause
    exit /b 1
)

echo.
echo [STATUS] Session ended.
pause
