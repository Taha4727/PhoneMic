@echo off
title PhoneMic Dependency Checker
color 0b

echo ===============================================================================
echo                PhoneMic Windows Receiver - Dependency Checker
echo ===============================================================================
echo.

:: 1. Check if Python is installed in system PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Python was not found in your system PATH!
    echo.
    echo PhoneMic requires Python 3.8+ to receive and decode microphone audio.
    echo Official Download: https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation!
    echo.
    set /p OPEN_BROWSER="Open Python download page in your web browser now? (Y/N): "
    if /i "%OPEN_BROWSER%"=="Y" (
        start https://www.python.org/downloads/
    )
    echo.
    pause
    exit /b 1
)

:: 2. Launch the interactive Python dependency checker
python "%~dp0check_dependencies.py"

if %errorlevel% neq 0 (
    echo.
    echo Dependency check finished.
    pause
)
