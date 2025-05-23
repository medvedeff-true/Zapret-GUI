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

:: Чтение general.bat
set "file=general.bat"
if not exist "!file!" (
  powershell -Command "Write-Host 'Файл general.bat не найден' -ForegroundColor Red"
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
sc stop zapret >nul 2>&1
sc delete zapret >nul 2>&1

:: Установка сервиса
sc create zapret binPath= "\"%BIN_PATH%winws.exe\"!args!" DisplayName= "zapret" start= auto
sc description zapret "Zapret DPI bypass software"
sc start zapret

:: Уведомление
powershell -Command "Write-Host 'Service successfully install.' -ForegroundColor Green"
timeout /t 5 /nobreak >nul
exit /b
