@echo off
title Build PhoneMicReceiver.exe (PyInstaller GUI Builder)
color 0b

echo ===============================================================================
echo            PhoneMic Windows Receiver - Standalone .EXE Builder (v0.7.5)
echo ===============================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0c
    echo [ERROR] Python was not found in your system PATH!
    echo Please install Python 3.8+ from python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 2. Check and install PyInstaller, sounddevice, and numpy
echo [*] Checking required build dependencies (pyinstaller, sounddevice, numpy)...
python -c "import PyInstaller, sounddevice, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing missing build packages via pip...
    python -m pip install pyinstaller sounddevice numpy
    if %errorlevel% neq 0 (
        color 0c
        echo [ERROR] Failed to install build packages. Check your internet connection.
        echo.
        pause
        exit /b 1
    )
)

echo [✓] Build environment ready.
echo.

:: 3. Clean up previous build outputs
echo [*] Cleaning old build directories...
if exist "%~dp0build" rd /s /q "%~dp0build"
if exist "%~dp0dist" rd /s /q "%~dp0dist"

:: 4. Build single-file EXE using PyInstaller spec file
echo [*] Compiling PhoneMicReceiver.exe with PyInstaller...
echo     This bundles Python, Tkinter GUI, PortAudio DLLs, NumPy, and SoundDevice into one standalone .exe.
echo.

pushd "%~dp0"
python -m PyInstaller --clean PhoneMicReceiver.spec
set BUILD_STATUS=%errorlevel%
popd

if %BUILD_STATUS% neq 0 (
    color 0c
    echo.
    echo [ERROR] PyInstaller build failed! Review the error messages above.
    echo.
    pause
    exit /b 1
)

:: 5. Verification
if not exist "%~dp0dist\PhoneMicReceiver.exe" (
    color 0c
    echo.
    echo [ERROR] PhoneMicReceiver.exe was not found in dist folder!
    echo.
    pause
    exit /b 1
)

:: Copy helper firewall script into dist for 1-click portability
copy /y "%~dp0fix_firewall.bat" "%~dp0dist\" >nul 2>&1

color 0a
echo.
echo ===============================================================================
echo [SUCCESS] PhoneMicReceiver.exe compiled successfully!
echo ===============================================================================
echo.
echo Location: %~dp0dist\PhoneMicReceiver.exe
echo.
echo Features included in your standalone .exe:
echo   - Self-contained (Runs on any Windows 10/11 PC without needing Python installed)
echo   - Sleek Native Dark GUI with real-time VU meter and live controls
echo   - Automatic resource pausing when minimized (0%% CPU / zero graphics rendering)
echo   - Subnet-aware USB Tethering and Wi-Fi IP auto-detection
echo   - Dynamic audio output switching (VB-CABLE / Speakers)
echo   - 1-click firewall configurator included (fix_firewall.bat)
echo.
echo Opening output folder...
explorer "%~dp0dist"
echo.
pause
