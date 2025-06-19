@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

set "LOCAL_VERSION=1.7.2b"
set "VERSION_URL=https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt"
set "REPO=https://github.com/Flowseal/zapret-discord-youtube"
set "ZIP_URL=%REPO%/archive/refs/tags/"
set "ZIP_PREFIX=zapret-discord-youtube-"
set "ZIP_SUFFIX=.zip"

:: Текущая директория GUI
cd /d "%~dp0"
cd ..\

echo [Обновление] Проверяем версию...
for /f "delims=" %%A in ('powershell -Command "(Invoke-WebRequest -Uri '%VERSION_URL%' -UseBasicParsing).Content.Trim()" 2^>nul') do set "REMOTE_VERSION=%%A"

if not defined REMOTE_VERSION (
    echo [Ошибка] Не удалось получить последнюю версию.
    goto end
)

echo Локальная версия: %LOCAL_VERSION%
echo Удалённая версия: %REMOTE_VERSION%

if "%REMOTE_VERSION%"=="%LOCAL_VERSION%" (
    echo Вы уже используете последнюю версию.
    goto end
)

echo [Обновление] Скачиваем архив %REMOTE_VERSION%...
set "ZIP_PATH=%TEMP%\%ZIP_PREFIX%%REMOTE_VERSION%%ZIP_SUFFIX%"
powershell -Command "Invoke-WebRequest -Uri '%ZIP_URL%%REMOTE_VERSION%%ZIP_SUFFIX%' -OutFile '%ZIP_PATH%'"

if not exist "%ZIP_PATH%" (
    echo [Ошибка] Не удалось скачать архив.
    goto end
)

echo [Обновление] Распаковываем...
set "UNPACK_DIR=%TEMP%\zapret_unpack"
rd /s /q "%UNPACK_DIR%" 2>nul
powershell -Command "Expand-Archive -LiteralPath '%ZIP_PATH%' -DestinationPath '%UNPACK_DIR%' -Force"

:: Путь к core из архива
for /d %%D in ("%UNPACK_DIR%\*") do (
    set "ARCHIVE_ROOT=%%~fD"
    goto got_root
)
:got_root

echo [Обновление] Копируем файлы в core\...
for /r "%ARCHIVE_ROOT%\core" %%F in (*) do (
    echo %%F | findstr /i "\\core\\fast\\" >nul
    if errorlevel 1 (
        set "DEST=core\%%~pF"
        set "DEST=!DEST:%ARCHIVE_ROOT%\core\=!"
        xcopy "%%F" "!DEST!" /Y /I >nul
        echo Обновлён: !DEST!%%~nxF
    )
)

echo.
powershell -Command "Write-Host '✅ Обновление завершено до версии %REMOTE_VERSION%' -ForegroundColor Green"

:end
echo.
echo Нажмите любую клавишу для выхода...
pause >nul
exit /b