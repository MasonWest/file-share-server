@echo off
chcp 65001 >nul
echo ========================================
echo   文件共享服务器启动程序
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖是否安装
echo 检查依赖安装...
pip list | findstr fastapi >nul
if errorlevel 1 (
    echo 安装依赖包...
    pip install -r requirements.txt
) else (
    echo 依赖已安装。
)

echo.
echo 启动文件共享服务器...
echo 共享目录配置: 请编辑 .env 文件中的 SHARE_DIR
echo 默认端口: 8800
echo 访问地址: http://localhost:8800
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

REM 启动服务器
python run_server.py

if errorlevel 1 (
    echo.
    echo [错误] 服务器启动失败
    echo 请检查:
    echo 1. Python依赖是否安装完整
    echo 2. .env文件中的SHARE_DIR路径是否正确
    echo 3. 端口8800是否被占用
    pause
)