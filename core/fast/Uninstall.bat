@echo off
setlocal EnableDelayedExpansion

:: —————————————————————————————————————————————————————
:: Поднятие прав администратора
net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

:: —————————————————————————————————————————————————————
echo.
echo [*] Попытка остановить и удалить службы zapret и zapret_discord...

:: Остановка и удаление службы zapret
sc stop zapret >nul 2>&1
timeout /t 1 /nobreak >nul
sc delete zapret >nul 2>&1

:: Остановка и удаление службы zapret_discord
sc stop zapret_discord >nul 2>&1
timeout /t 1 /nobreak >nul
sc delete zapret_discord >nul 2>&1

:: Остановка и удаление драйверов WinDivert (если есть)
net stop "WinDivert" >nul 2>&1 & sc delete "WinDivert" >nul 2>&1
net stop "WinDivert14" >nul 2>&1 & sc delete "WinDivert14" >nul 2>&1

:: —————————————————————————————————————————————————————
echo.
powershell -Command "Write-Host 'Services successfuly removed' -ForegroundColor Green"
timeout /t 3 /nobreak >nul
exit /b
