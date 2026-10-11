@echo off
title PhoneMic Windows Firewall Configurator
color 0b

echo ===============================================================================
echo            PhoneMic Windows Firewall Fixer (USB Tether + Wi-Fi)
echo ===============================================================================
echo.

:: Check for Administrator elevation
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Administrator permissions are required to configure firewall rules.
    echo [*] Elevating to Administrator now...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo [*] Adding Inbound UDP 5001 Rule (Profile=ALL: Private, Public, Domain)...
netsh advfirewall firewall delete rule name="PhoneMic Receiver (UDP 5001)" >nul 2>&1
netsh advfirewall firewall add rule name="PhoneMic Receiver (UDP 5001)" dir=in action=allow protocol=UDP localport=5001 profile=any enable=yes

echo [*] Adding Inbound TCP 5001 Rule (Profile=ALL: Private, Public, Domain)...
netsh advfirewall firewall delete rule name="PhoneMic Receiver (TCP 5001)" >nul 2>&1
netsh advfirewall firewall add rule name="PhoneMic Receiver (TCP 5001)" dir=in action=allow protocol=TCP localport=5001 profile=any enable=yes

:: If PhoneMicReceiver.exe exists in directory or dist, add application rules too
if exist "%~dp0PhoneMicReceiver.exe" (
    echo [*] Adding Program Rule for PhoneMicReceiver.exe...
    netsh advfirewall firewall delete rule name="PhoneMic Receiver App" >nul 2>&1
    netsh advfirewall firewall add rule name="PhoneMic Receiver App" dir=in action=allow program="%~dp0PhoneMicReceiver.exe" profile=any enable=yes
)

if exist "%~dp0dist\PhoneMicReceiver.exe" (
    echo [*] Adding Program Rule for dist\PhoneMicReceiver.exe...
    netsh advfirewall firewall delete rule name="PhoneMic Receiver App Dist" >nul 2>&1
    netsh advfirewall firewall add rule name="PhoneMic Receiver App Dist" dir=in action=allow program="%~dp0dist\PhoneMicReceiver.exe" profile=any enable=yes
)

color 0a
echo.
echo ===============================================================================
echo [SUCCESS] Windows Defender Firewall configured for PhoneMic!
echo ===============================================================================
echo.
echo Both Wi-Fi and USB Tethering (Public Profile) connections are now allowed.
echo You can now connect PhoneMic smoothly without any dropped audio packets.
echo.
pause
