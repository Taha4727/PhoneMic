@echo off
title PhoneMic Windows Firewall Configurator
color 0b

:: Usage: fix_firewall.bat [port]      (default 5001 - use the port shown on the Network page)
set "PM_PORT=%~1"
if "%PM_PORT%"=="" set "PM_PORT=5001"

echo ===============================================================================
echo        PhoneMic Windows Firewall Fixer  (USB tether + Wi-Fi)     port %PM_PORT%
echo ===============================================================================
echo.

net session >nul 2>&1
if not errorlevel 1 goto :admin
echo [!] Administrator permission is required to change firewall rules.
echo [*] Asking Windows for elevation...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '%PM_PORT%' -Verb RunAs"
exit /b

:admin
echo [*] Inbound UDP %PM_PORT% (all network profiles)
netsh advfirewall firewall delete rule name="PhoneMic Receiver (UDP %PM_PORT%)" >nul 2>&1
netsh advfirewall firewall add rule name="PhoneMic Receiver (UDP %PM_PORT%)" dir=in action=allow protocol=UDP localport=%PM_PORT% profile=any enable=yes

echo [*] Inbound TCP %PM_PORT% (all network profiles)
netsh advfirewall firewall delete rule name="PhoneMic Receiver (TCP %PM_PORT%)" >nul 2>&1
netsh advfirewall firewall add rule name="PhoneMic Receiver (TCP %PM_PORT%)" dir=in action=allow protocol=TCP localport=%PM_PORT% profile=any enable=yes

if exist "%~dp0PhoneMicReceiver.exe" call :progrule "PhoneMic Receiver App" "%~dp0PhoneMicReceiver.exe"
if exist "%~dp0dist\PhoneMicReceiver.exe" call :progrule "PhoneMic Receiver App Dist" "%~dp0dist\PhoneMicReceiver.exe"

color 0a
echo.
echo ===============================================================================
echo [SUCCESS] Windows Firewall is configured for PhoneMic (port %PM_PORT%)
echo ===============================================================================
echo Wi-Fi and USB tethering connections ("Public" profile) are now allowed.
echo.
pause
exit /b 0

:progrule
echo [*] Program rule: %~2
netsh advfirewall firewall delete rule name=%1 >nul 2>&1
netsh advfirewall firewall add rule name=%1 dir=in action=allow program=%2 profile=any enable=yes
exit /b 0
