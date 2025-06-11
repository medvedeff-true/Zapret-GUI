@echo off
rem — Ждём 2 секунды перед удалением (_MEI* иногда ещё заняты)
timeout /t 2 /nobreak >nul

setlocal enabledelayedexpansion
for /f "delims=" %%d in ('dir /b /ad "%TEMP%\_MEI*"') do (
    rd /s /q "%TEMP%\%%d"
)
endlocal
exit /b 0
