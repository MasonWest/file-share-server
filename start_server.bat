@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo File Share Server
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Install Python 3.7+ and try again.
    pause
    exit /b 1
)

python -c "import fastapi, uvicorn, dotenv, multipart" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies from requirements.txt ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Starting server ...
python run_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with an error.
    pause
    exit /b 1
)

endlocal
