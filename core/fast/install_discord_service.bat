@echo off
setlocal EnableDelayedExpansion

:: Поднятие прав
net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

:: Переход в core
cd /d "%~dp0\.."

set "BIN_PATH=%CD%\bin\"
set "LISTS_PATH=%CD%\lists\"

:: Чтение discord.bat
set "file=discord.bat"
if not exist "!file!" (
  powershell -Command "Write-Host 'Файл discord.bat не найден' -ForegroundColor Red"
  timeout /t 5 /nobreak >nul
  exit /b
)

:: Поиск строки запуска winws.exe
set "args="
for /f "tokens=*" %%A in ('findstr /i /c:"winws.exe" "!file!"') do set "line=%%A"

:: Парсинг строки
for %%a in (!line!) do (
  set "token=%%~a"
  if /i "!token!" neq "start" if /i "!token!" neq "start" if /i "!token:~-8!" neq "winws.exe" (
    set "args=!args! !token!"
  )
)

:: Удаление предыдущего сервиса
sc stop zapret_discord >nul 2>&1
sc delete zapret_discord >nul 2>&1

:: Установка сервиса
sc create zapret_discord binPath= "\"%BIN_PATH%winws.exe\"!args!" DisplayName= "zapret_discord" start= auto
sc description zapret_discord "Zapret DPI bypass for Discord"
sc start zapret_discord

:: Уведомление
powershell -Command "Write-Host 'Discord service successfully installed.' -ForegroundColor Green"
timeout /t 5 /nobreak >nul
exit /b
