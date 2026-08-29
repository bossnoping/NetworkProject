@echo off
setlocal
pushd "%~dp0.."

echo ===================================================
echo   SRMP Server - Launcher & Auto Setup
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

echo [SRMP] Starting SRMP Server...
call .venv\Scripts\python server\srmp_server.py %*

popd

