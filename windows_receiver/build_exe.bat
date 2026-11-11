@echo off
title Build PhoneMicReceiver.exe (PyInstaller)
color 0b

echo ===============================================================================
echo            PhoneMic Windows Receiver - Standalone .EXE Builder (v1.2.0)
echo ===============================================================================
echo.
echo   build_exe.bat            single portable .exe   (starts in a few seconds)
echo   build_exe.bat onedir     folder build            (starts instantly, used by the installer)
echo.

set "PM_ONEDIR="
set "PM_NOPAUSE="
if /i "%~1"=="onedir" set "PM_ONEDIR=1"
if /i "%~1"=="nopause" set "PM_NOPAUSE=1"
if /i "%~2"=="nopause" set "PM_NOPAUSE=1"

:: 1. Python
python --version >nul 2>&1
if errorlevel 1 goto :no_python

:: 2. Build dependencies
echo [*] Checking build dependencies (pyinstaller, sounddevice, numpy, pystray, pillow)...
python -c "import PyInstaller, sounddevice, numpy, pystray, PIL" >nul 2>&1
if not errorlevel 1 goto :deps_ok
echo [*] Installing missing packages via pip...
python -m pip install pyinstaller sounddevice numpy pystray pillow
if errorlevel 1 goto :pip_failed
:deps_ok
echo [OK] Build environment ready.
echo.

:: 3. Clean
echo [*] Cleaning old build output...
if exist "%~dp0build" rd /s /q "%~dp0build"
if exist "%~dp0dist" rd /s /q "%~dp0dist"

:: 4. Build
if defined PM_ONEDIR (echo [*] Building folder version...) else (echo [*] Building single-file version...)
pushd "%~dp0"
python -m PyInstaller --clean PhoneMicReceiver.spec
set BUILD_STATUS=%errorlevel%
popd
if not "%BUILD_STATUS%"=="0" goto :build_failed

set "OUT=%~dp0dist\PhoneMicReceiver.exe"
if defined PM_ONEDIR set "OUT=%~dp0dist\PhoneMicReceiver\PhoneMicReceiver.exe"
if not exist "%OUT%" goto :missing_output

copy /y "%~dp0fix_firewall.bat" "%~dp0dist\" >nul 2>&1

color 0a
echo.
echo ===============================================================================
echo [SUCCESS] Build finished
echo ===============================================================================
echo.
echo   Output: %OUT%
echo.
echo   - Runs on any Windows 10/11 PC without Python
echo   - Settings are saved next to the .exe, or in %%LOCALAPPDATA%%\PhoneMic if that folder is read-only
echo   - fix_firewall.bat was copied into dist\ - run it once if USB tethering stays silent
echo.
if not defined PM_NOPAUSE explorer "%~dp0dist"
if not defined PM_NOPAUSE pause
exit /b 0

:no_python
color 0c
echo [ERROR] Python was not found in your system PATH.
echo Install Python 3.8 or newer from python.org and tick "Add Python to PATH".
echo.
if not defined PM_NOPAUSE pause
exit /b 1

:pip_failed
color 0c
echo [ERROR] Could not install the build packages. Check your internet connection.
echo.
if not defined PM_NOPAUSE pause
exit /b 1

:build_failed
color 0c
echo.
echo [ERROR] PyInstaller failed. Read the messages above.
echo.
if not defined PM_NOPAUSE pause
exit /b 1

:missing_output
color 0c
echo.
echo [ERROR] The build finished but the expected file is missing:
echo %OUT%
echo.
if not defined PM_NOPAUSE pause
exit /b 1
