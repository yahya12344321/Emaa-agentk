@echo off
setlocal EnableExtensions EnableDelayedExpansion
title EMAA Launcher
cd /d "%~dp0"
set "STATUS_FILE=%~dp0.emaa-launch-status"

if exist "%STATUS_FILE%" del /f /q "%STATUS_FILE%" >nul 2>nul

echo ===============================================
echo EMAA Launcher
echo Project: %~dp0
echo Main launcher: tools\launch_emaa.ps1
echo ===============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch_emaa.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if exist "%STATUS_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%STATUS_FILE%") do (
        if /I "%%A"=="MODE" set "EMAA_MODE=%%B"
        if /I "%%A"=="URL" set "EMAA_URL=%%B"
        if /I "%%A"=="BACKEND_AVAILABLE" set "EMAA_BACKEND=%%B"
        if /I "%%A"=="DETAILS" set "EMAA_DETAILS=%%B"
    )

    echo.
    if /I "!EMAA_MODE!"=="full" (
        echo [OK] EMAA is running in FULL mode.
        echo [OK] Sign-to-text backend is active.
        if defined EMAA_URL echo [OK] Opened at: !EMAA_URL!
    ) else if /I "!EMAA_MODE!"=="static" (
        echo [WARN] EMAA is running in BROWSER-ONLY mode.
        echo [WARN] Sign-to-text backend is NOT active in this mode.
        if defined EMAA_URL echo [OK] Opened at: !EMAA_URL!
    ) else if /I "!EMAA_MODE!"=="failed" (
        echo [ERROR] EMAA did not start successfully.
    )

    if defined EMAA_DETAILS echo [INFO] !EMAA_DETAILS!
)

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] EMAA could not be started successfully.
    echo Check the server window for details, then try again.
    pause
)

exit /b %EXIT_CODE%
