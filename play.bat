@echo off
REM DEADSHIFT — One-command launcher for Windows
REM Usage: play.bat              (join a game)
REM        play.bat host         (host a game + play)
REM        play.bat admin        (host + admin/QA mode)
REM
REM Just double-click this file or run: play.bat

cd /d "%~dp0"

echo.
echo   ____  _____    _    ____  ____  _   _ ___ _____ _____
echo  ^|  _ \^| ____^|  / \  ^|  _ \/ ___^|^| ^| ^| ^|_ _^|  ___^|_   _^|
echo  ^| ^| ^| ^|  _^|   / _ \ ^| ^| ^| \___ \^| ^|_^| ^|^| ^|^| ^|_    ^| ^|
echo  ^| ^|_^| ^| ^|___ / ___ \^| ^|_^| ^|___) ^|  _  ^|^| ^|^|  _^|   ^| ^|
echo  ^|____/^|_____/_/   \_\____/^|____/^|_^| ^|_^|___^|_^|     ^|_^|
echo.

REM ── Find Python ───────────────────────────────────────────────────
set PYTHON=
where python3 >nul 2>&1 && set PYTHON=python3
if "%PYTHON%"=="" (where python >nul 2>&1 && set PYTHON=python)

if "%PYTHON%"=="" (
    echo.
    echo   ERROR: Python 3 is required but not found.
    echo.
    echo   Install it from: https://python.org/downloads
    echo   IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)

echo   Python: found
%PYTHON% --version

REM ── Install deps if needed ────────────────────────────────────────
%PYTHON% -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo   Installing game dependencies (one-time^)...
    %PYTHON% -m pip install -r requirements.txt --quiet
    echo   Done.
) else (
    echo   Dependencies: OK
)

REM ── HOST MODE ─────────────────────────────────────────────────────
if "%1"=="host" goto HOST
if "%1"=="admin" goto HOST
goto PLAYER

:HOST
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Node.js is required to HOST (not to play^).
    echo   Install it from: https://nodejs.org
    echo.
    pause
    exit /b 1
)

echo   Node.js: found

if not exist "node_modules" (
    echo   Installing server dependencies (one-time^)...
    npm install --silent
)

REM Kill existing server on port 3000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Start server
start /b node server.js

REM Wait for server
timeout /t 2 /nobreak >nul

REM Get local IP
set IP=localhost
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" 2^>nul') do (
    for /f "tokens=1" %%b in ("%%a") do set IP=%%b
)

echo.
echo   ===================================================
echo.
echo   SERVER RUNNING
echo.
echo   Tell your coworkers this address:
echo.
echo       %IP%:3000
echo.
echo   They enter it in the Server field in-game.
echo.
echo   ===================================================
echo.

set EXTRA_ARGS=--server %IP%:3000
if "%1"=="admin" set EXTRA_ARGS=%EXTRA_ARGS% --admin

%PYTHON% game.py %EXTRA_ARGS%

REM Cleanup — kill node server
taskkill /f /im node.exe >nul 2>&1
echo   Server stopped.
goto END

:PLAYER
echo.
echo   Launching DEADSHIFT...
echo   Enter the server IP your host gave you.
echo.
%PYTHON% game.py
goto END

:END
pause
