@echo off
title Build PhoneMic Receiver installer
color 0b

echo ===============================================================================
echo            PhoneMic Receiver - installer builder
echo ===============================================================================
echo.
echo  Needs Inno Setup 6 (free): https://jrsoftware.org/isdl.php
echo.

:: 1. Build the program folder (no prompts)
call "%~dp0..\build_exe.bat" onedir nopause
if errorlevel 1 goto :fail_build

:: 2. Find the Inno Setup compiler
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :compile
set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :compile
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :compile
goto :no_inno

:compile
echo [*] Compiling the installer...
"%ISCC%" "%~dp0PhoneMicReceiver.iss"
if errorlevel 1 goto :fail_compile

color 0a
echo.
echo ===============================================================================
echo [SUCCESS] The installer is in the installer-output folder.
echo ===============================================================================
explorer "%~dp0..\installer-output"
pause
exit /b 0

:no_inno
color 0c
echo [ERROR] Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php and run this again.
pause
exit /b 1

:fail_build
color 0c
echo [ERROR] Building the program failed. Read the messages above.
pause
exit /b 1

:fail_compile
color 0c
echo [ERROR] Inno Setup reported an error. Read the messages above.
pause
exit /b 1
