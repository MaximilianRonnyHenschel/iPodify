@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe gui.py
    pause REM Added pause here
) else (
    echo Virtual environment not found. Please run setup first.
    pause
)
