@echo off
REM ================================================================
REM  Forecast-Bust Sentinel — One-Click Launcher
REM  Starts both backend API + frontend dashboard on localhost:8001
REM ================================================================
title Forecast-Bust Sentinel — localhost:8001

echo.
echo ============================================================
echo   Forecast-Bust Sentinel — Launcher
echo ============================================================
echo.

REM Navigate to the project root (same directory as this .bat file)
cd /d "%~dp0"

REM ---------------------------------------------------------------
REM 1. Check Python is available
REM ---------------------------------------------------------------
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo         Please install Python 3.9+ and add it to PATH.
    echo.
    pause
    exit /b 1
)

echo [1/3] Python found:
python --version
echo.

REM ---------------------------------------------------------------
REM 2. Install dependencies (pip install -r requirements.txt + flask)
REM ---------------------------------------------------------------
echo [2/3] Installing dependencies...
pip install -r requirements.txt --quiet 2>nul
pip install flask flask-cors --quiet 2>nul
echo       Done.
echo.

REM ---------------------------------------------------------------
REM 3. Launch the server on port 8001
REM ---------------------------------------------------------------
echo [3/3] Starting server on http://localhost:8001 ...
echo.
echo ============================================================
echo   Dashboard : http://localhost:8001/
echo   Health API: http://localhost:8001/api/health
echo   Locations : http://localhost:8001/api/locations
echo ============================================================
echo.
echo   Press Ctrl+C to stop the server.
echo.

python server.py

REM If we get here, the server stopped
echo.
echo Server stopped.
pause
