@echo off
title PhoneMic Windows Receiver v0.6.1
color 0b
echo ===============================================================================
echo                   PhoneMic Windows Receiver Setup ^& Launcher
echo ===============================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.9+ from python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo [*] Checking required Python audio libraries (sounddevice, numpy)...
python -c "import sounddevice, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing missing audio libraries...
    pip install sounddevice numpy
    if %errorlevel% neq 0 (
        color 0c
        echo [ERROR] Failed to install packages. Check your internet connection.
        pause
        exit /b 1
    )
)

echo.
echo [OK] Dependencies verified. Starting PhoneMic Receiver...
echo.
python "%~dp0phonemic_receiver.py"

if %errorlevel% neq 0 (
    echo.
    echo Receiver exited with an error.
    pause
)
