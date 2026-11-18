@echo off
setlocal EnableDelayedExpansion
title Nexus AI Orchestrator - Automated Environment Setup

echo ============================================================================
echo   NEXUS AI ORCHESTRATOR - AUTOMATED WORKSTATION SETUP
echo ============================================================================
echo.

:: 1. Verify Python installation
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [1/5] Detected %PYVER%

:: 2. Create isolated virtual environment (.venv)
if not exist ".venv\Scripts\activate.bat" (
    echo [2/5] Creating isolated Python virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/5] Existing virtual environment (.venv) found.
)

:: 3. Activate virtual environment and upgrade pip
echo [3/5] Activating virtual environment and upgrading pip...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel

:: 4. Install required modules (PyQt6, PyQt6-WebEngine)
echo [4/5] Downloading and installing PyQt6 and Chromium WebEngine modules...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    pip install PyQt6 PyQt6-WebEngine
)

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install required Python packages. Check your internet connection.
    pause
    exit /b 1
)

:: 5. Verify core modules and create run_nexus.bat launcher
echo [5/5] Verifying Nexus AI Orchestrator modules...
python -c "import PyQt6.QtWidgets, PyQt6.QtWebEngineWidgets; print('[OK] PyQt6 & QtWebEngine verified successfully!')"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Module verification failed.
    pause
    exit /b 1
)

:: Create one-click launcher script
(
echo @echo off
echo cd /d "%%~dp0"
echo call ".venv\Scripts\activate.bat"
echo python main.py
) > run_nexus.bat

echo.
echo ============================================================================
echo   SETUP COMPLETE!
echo   - To launch anytime, double-click: run_nexus.bat
echo   - Starting Nexus AI Orchestrator for initial account onboarding...
echo ============================================================================
echo.
python main.py
pause