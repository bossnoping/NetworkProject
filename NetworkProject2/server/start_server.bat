@echo off
setlocal
pushd "%~dp0.."

:: Check for Administrative Privileges (required for direct CPU Temperature hardware sensor access)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [SRMP] Elevating to Administrator privileges for hardware sensor access...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ===================================================
echo   SRMP Server - Launcher & Auto Setup (Admin)
echo ===================================================

:: Check if Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.10+ from python.org and check "Add to PATH".
    pause
    exit /b 1
)

:: Check if .venv exists, if not create and install dependencies
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] First time setup: Creating virtual environment (.venv)...
    python -m venv .venv
    echo [SETUP] Installing required packages from requirements.txt...
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r server\requirements.txt
    echo [SETUP] Dependencies installed successfully!
)

:: Release port 9001 if previously occupied by a stale process
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":9001" ^| findstr "LISTENING"') do (
    echo [SRMP] Releasing port 9001 from PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

echo [SRMP] Starting SRMP Server...
.venv\Scripts\python.exe server\srmp_server.py %*

popd

