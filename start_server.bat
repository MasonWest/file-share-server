@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo File Share Server
echo ========================================
echo.
echo Admin panel: http://YOUR_SERVER_IP:8800
echo Public download: http://YOUR_SERVER_IP:9900
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.7+ and try again.
    pause
    exit /b 1
)

echo Starting dual-port server ...
python run_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with an error.
    pause
    exit /b 1
)

endlocal
