@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

:: —————————————————————————————————————————————————————
:: Elevate privileges
net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

:: —————————————————————————————————————————————————————
echo.
echo === [1] Checking service status ===
call :check_status
timeout /t 1 /nobreak >nul

:: Check if bypass is active (winws.exe is running)
tasklist /FI "IMAGENAME eq winws.exe" | find /I "winws.exe" > nul
if !errorlevel!==0 (
    powershell -Command "Write-Host 'Unable to remove services because bypass is currently active. Please disable it via the GUI first.' -ForegroundColor Red"
    timeout /t 5 /nobreak >nul
    exit /b
)

echo.
echo === [2] Removing services ===
call :remove_services
timeout /t 1 /nobreak >nul

echo.
echo === [3] Running diagnostics ===
call :run_diagnostics
timeout /t 1 /nobreak >nul

echo.
echo === [4] Final service status check ===
call :check_status
timeout /t 1 /nobreak >nul

powershell -Command "Write-Host 'Success' -ForegroundColor Green"
timeout /t 5 /nobreak >nul
exit /b

:: —————————————————————————————————————————————————————
:check_status
tasklist /FI "IMAGENAME eq winws.exe" | find /I "winws.exe" > nul
if !errorlevel!==0 (
    powershell -Command "Write-Host '[+] winws.exe is running' -ForegroundColor Yellow"
) else (
    powershell -Command "Write-Host '[-] winws.exe is not running' -ForegroundColor Gray"
)

sc query zapret | findstr /i "STATE"
sc query WinDivert | findstr /i "STATE"
sc query WinDivert14 | findstr /i "STATE"
exit /b

:: —————————————————————————————————————————————————————
:remove_services
echo [*] Attempting to remove services: zapret and zapret_discord...

sc stop zapret >nul 2>&1
sc delete zapret >nul 2>&1
sc stop zapret_discord >nul 2>&1
sc delete zapret_discord >nul 2>&1

net stop "WinDivert" >nul 2>&1 & sc delete "WinDivert" >nul 2>&1
net stop "WinDivert14" >nul 2>&1 & sc delete "WinDivert14" >nul 2>&1
exit /b

:: —————————————————————————————————————————————————————
:run_diagnostics
echo Running diagnostics...

:: Adguard
tasklist /FI "IMAGENAME eq AdguardSvc.exe" | find /I "AdguardSvc.exe" > nul
if !errorlevel!==0 (
    call :PrintRed "[X] Adguard detected"
) else (
    call :PrintGreen "[✓] Adguard check passed"
)

:: Killer
sc query | findstr /I "Killer" > nul
if !errorlevel!==0 (
    call :PrintRed "[X] Killer service found"
) else (
    call :PrintGreen "[✓] Killer check passed"
)

:: Check Point
set "checkpoint=0"
sc query | findstr /I "TracSrvWrapper" > nul && set checkpoint=1
sc query | findstr /I "EPWD" > nul && set checkpoint=1
if !checkpoint!==1 (
    call :PrintRed "[X] Check Point found"
) else (
    call :PrintGreen "[✓] Check Point check passed"
)

:: SmartByte
sc query | findstr /I "SmartByte" > nul
if !errorlevel!==0 (
    call :PrintRed "[X] SmartByte detected"
) else (
    call :PrintGreen "[✓] SmartByte check passed"
)

:: VPN
sc query | findstr /I "VPN" > nul
if !errorlevel!==0 (
    call :PrintYellow "[?] VPN services may be active"
) else (
    call :PrintGreen "[✓] VPN check passed"
)

:: DNS
set "dnsfound=0"
for /f "skip=1 tokens=*" %%a in ('wmic nicconfig where "IPEnabled=true" get DNSServerSearchOrder /format:table') do (
    echo %%a | findstr /i "192.168." >nul
    if !errorlevel!==1 (
        set "dnsfound=1"
    )
)
if !dnsfound!==0 (
    call :PrintYellow "[?] DNS may be using provider defaults"
) else (
    call :PrintGreen "[✓] DNS check passed"
)

exit /b

:: —————————————————————————————————————————————————————
:PrintGreen
powershell -Command "Write-Host \"%~1\" -ForegroundColor Green"
exit /b

:PrintRed
powershell -Command "Write-Host \"%~1\" -ForegroundColor Red"
exit /b

:PrintYellow
powershell -Command "Write-Host \"%~1\" -ForegroundColor Yellow"
exit /b
