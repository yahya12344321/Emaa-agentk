@echo off
setlocal
title EMAA Mobile Server
cd /d "%~dp0"

set "NODE_EXE="
where node >nul 2>nul
if not errorlevel 1 set "NODE_EXE=node"
if "%NODE_EXE%"=="" if exist "C:\Users\kk200\AppData\Local\OpenAI\Codex\bin\node.exe" set "NODE_EXE=C:\Users\kk200\AppData\Local\OpenAI\Codex\bin\node.exe"
if "%NODE_EXE%"=="" if exist "C:\Users\kk200\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" set "NODE_EXE=C:\Users\kk200\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

if "%NODE_EXE%"=="" (
    echo.
    echo [ERROR] Node.js is not available from this window.
    echo Install Node.js from https://nodejs.org, then open this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting EMAA for mobile...
echo Keep this window open while using the site on your phone.
echo If Windows Firewall asks, choose Allow access.
echo.

"%NODE_EXE%" "%~dp0tools\mobile_static_server.js" 8080

pause
