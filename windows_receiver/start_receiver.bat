@echo off
title PhoneMic Windows Receiver v0.6.5
color 0b
echo ===============================================================================
echo                   PhoneMic Windows Receiver Setup ^& Launcher
echo ===============================================================================
echo.

:: 1. If compiled .exe exists, launch it directly!
if exist "%~dp0PhoneMicReceiver.exe" (
    echo [*] Launching standalone PhoneMicReceiver.exe...
    "%~dp0PhoneMicReceiver.exe" %*
    goto :done
)

if exist "%~dp0dist\PhoneMicReceiver.exe" (
    echo [*] Launching standalone dist\PhoneMicReceiver.exe...
    "%~dp0dist\PhoneMicReceiver.exe" %*
    goto :done
)

:: 2. Otherwise run via Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python from python.org (check "Add Python to PATH"),
    echo or compile PhoneMicReceiver.exe using build_exe.bat.
    echo.
    pause
    exit /b 1
)

:: 3. Launch unified receiver (handles dependency cache & auto-install silently)
python "%~dp0phonemic_receiver.py" %*

:done
if %errorlevel% neq 0 (
    echo.
    echo Receiver exited.
    pause
)
