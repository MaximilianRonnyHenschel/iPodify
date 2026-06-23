@echo off
setlocal
cd /d "%~dp0"

REM --- Check for Python ---
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed or not on PATH. Please install Python 3 and try again.
    pause
    exit /b 1
)

REM --- Create Virtual Environment if it doesn't exist ---
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM --- Install dependencies ---
echo Installing dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

REM --- Run the application ---
echo Starting the application...
.venv\Scripts\python.exe gui.py

echo.
echo Application finished.
pause
