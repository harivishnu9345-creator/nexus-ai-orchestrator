@echo off
setlocal
cd /d "%~dp0"
title Nexus AI Orchestrator - Automated Environment Setup

echo ============================================================================
echo   NEXUS AI ORCHESTRATOR - AUTOMATED WORKSTATION SETUP
echo ============================================================================
echo.

:: 1. Verify Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [1/5] Detected %PYVER%

:: Auto-create requirements.txt if setup.bat was copied alone
if not exist "requirements.txt" (
    echo PyQt6>=6.6.0> requirements.txt
    echo PyQt6-WebEngine>=6.6.0>> requirements.txt
)

:: 2. Create isolated virtual environment (.venv) without parenthesized blocks
if exist ".venv\Scripts\python.exe" goto :VENV_READY
echo [2/5] Creating isolated Python virtual environment in .venv ...
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
goto :VENV_DONE

:VENV_READY
echo [2/5] Existing virtual environment found in .venv

:VENV_DONE

:: 3. Upgrade pip inside the virtual environment directly
echo [3/5] Upgrading pip, setuptools, and wheel...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [WARNING] Pip upgrade returned a non-zero code, continuing with package installation...
)

:: 4. Install required modules (PyQt6, PyQt6-WebEngine)
echo [4/5] Downloading and installing PyQt6 and Chromium WebEngine modules...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install required Python packages. Check your internet connection.
    pause
    exit /b 1
)

:: 5. Verify core modules and create run_nexus.bat launcher
echo [5/5] Verifying Nexus AI Orchestrator modules...
".venv\Scripts\python.exe" -c "import PyQt6.QtWidgets, PyQt6.QtWebEngineWidgets; print('[OK] PyQt6 and QtWebEngine verified successfully!')"
if errorlevel 1 (
    echo [ERROR] Module verification failed.
    pause
    exit /b 1
)

:: Create one-click launcher script
echo @echo off> run_nexus.bat
echo cd /d "%%~dp0">> run_nexus.bat
echo ".venv\Scripts\python.exe" main.py>> run_nexus.bat
echo if errorlevel 1 pause>> run_nexus.bat

echo.
echo ============================================================================
echo   SETUP COMPLETE!
echo   - To launch anytime, double-click: run_nexus.bat
echo ============================================================================
echo.

if exist "main.py" (
    echo Launching Nexus AI Orchestrator...
    ".venv\Scripts\python.exe" main.py
) else (
    echo [NOTE] main.py was not found in this folder: %CD%
    echo Make sure main.py, config.json, core\, and ui\ are in this same folder!
)

pause