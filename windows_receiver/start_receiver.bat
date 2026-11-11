@echo off
title PhoneMic Windows Receiver v1.2.0
color 0b

:: 1. A compiled .exe next to this script wins
if exist "%~dp0PhoneMicReceiver.exe" start "" "%~dp0PhoneMicReceiver.exe" %* & exit /b 0
if exist "%~dp0dist\PhoneMicReceiver.exe" start "" "%~dp0dist\PhoneMicReceiver.exe" %* & exit /b 0
if exist "%~dp0dist\PhoneMicReceiver\PhoneMicReceiver.exe" start "" "%~dp0dist\PhoneMicReceiver\PhoneMicReceiver.exe" %* & exit /b 0

:: 2. Otherwise run from source
python --version >nul 2>&1
if errorlevel 1 goto :no_python

python -c "import numpy, sounddevice, pystray, PIL" >nul 2>&1
if not errorlevel 1 goto :run
echo [*] Installing packages (numpy, sounddevice, and pystray and pillow for the tray icon)...
python -m pip install -r "%~dp0requirements.txt"

:run
:: Console mode keeps this window; the GUI starts without a console (pythonw).
echo %* | find /i "--cli" >nul
if not errorlevel 1 goto :console
where pythonw >nul 2>&1
if errorlevel 1 goto :console
start "" pythonw "%~dp0phonemic_receiver.py" %*
exit /b 0

:console
python "%~dp0phonemic_receiver.py" %*
pause
exit /b 0

:no_python
color 0c
echo [ERROR] Python is not installed or not in PATH.
echo Install it from python.org and tick "Add Python to PATH", or build the .exe with build_exe.bat.
echo.
pause
exit /b 1
