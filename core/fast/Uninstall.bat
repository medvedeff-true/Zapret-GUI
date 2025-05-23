@echo off

:: —————————————————————————————————————————————————————
:: Поднятие прав
net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

:: —————————————————————————————————————————————————————
:: Останавливаем и удаляем сервисы
sc stop zapret   >nul 2>&1
sc delete zapret >nul 2>&1

net stop "WinDivert"   >nul 2>&1 & sc delete "WinDivert"   >nul 2>&1
net stop "WinDivert14" >nul 2>&1 & sc delete "WinDivert14" >nul 2>&1

:: —————————————————————————————————————————————————————
:: Уведомление об успехе
powershell -Command "Write-Host 'Service successfully removed.' -ForegroundColor Green"
timeout /t 5 /nobreak >nul
exit /b
