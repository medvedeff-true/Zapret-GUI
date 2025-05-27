@echo off
setlocal EnableDelayedExpansion

:: — Повышаем права до администратора
net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

:: — Переходим в папку core
cd /d "%~dp0\.."

set "BIN_PATH=%CD%\bin\"
set "LISTS_PATH=%CD%\lists\"

:: — Файл профиля Discord
set "file=discord.bat"
if not exist "!file!" (
  powershell -Command "Write-Host 'Файл discord.bat не найден' -ForegroundColor Red"
  timeout /t 5 /nobreak >nul
  exit /b
)

:: — Ищем строку запуска winws.exe внутри discord.bat
set "args="
for /f "tokens=*" %%A in ('findstr /i /c:"winws.exe" "!file!"') do set "line=%%A"

:: — Парсим всё после winws.exe (флаги и параметры)
for %%a in (!line!) do (
  set "token=%%~a"
  if /i "!token:~-8!" neq "winws.exe" if /i "!token!" neq "start" (
    set "args=!args! !token!"
  )
)

:: — Удаляем прошлую службу zapret, если она есть
sc stop zapret >nul 2>&1
sc delete zapret >nul 2>&1

:: — Создаём новую службу zapret с аргументами из discord.bat
sc create zapret ^
    binPath= "\"%BIN_PATH%winws.exe\"!args!" ^
    DisplayName= "zapret" start= auto
sc description zapret "Zapret DPI bypass software"

:: — Запускаем службу
sc start zapret

:: — Уведомление об успехе
powershell -Command "Write-Host 'Discord service installed' -ForegroundColor Green"
timeout /t 5 /nobreak >nul
exit /b
