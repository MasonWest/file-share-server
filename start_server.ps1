# 文件共享服务器启动脚本 (PowerShell)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   文件共享服务器启动程序" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python是否安装
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未找到Python，请先安装Python 3.7+" -ForegroundColor Red
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按Enter键退出"
    exit 1
}

# 检查依赖是否安装
Write-Host "检查依赖安装..." -ForegroundColor Yellow
$fastapiInstalled = pip list | Select-String "fastapi"
if (-not $fastapiInstalled) {
    Write-Host "安装依赖包..." -ForegroundColor Yellow
    pip install -r requirements.txt
} else {
    Write-Host "依赖已安装。" -ForegroundColor Green
}

Write-Host ""
Write-Host "启动文件共享服务器..." -ForegroundColor Cyan
Write-Host "共享目录配置: 请编辑 .env 文件中的 SHARE_DIR" -ForegroundColor Yellow
Write-Host "默认端口: 8800" -ForegroundColor Yellow
Write-Host "访问地址: http://localhost:8800" -ForegroundColor Yellow
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 启动服务器
try {
    python run_server.py
} catch {
    Write-Host ""
    Write-Host "[错误] 服务器启动失败" -ForegroundColor Red
    Write-Host "请检查:" -ForegroundColor Yellow
    Write-Host "1. Python依赖是否安装完整" -ForegroundColor Yellow
    Write-Host "2. .env文件中的SHARE_DIR路径是否正确" -ForegroundColor Yellow
    Write-Host "3. 端口8800是否被占用" -ForegroundColor Yellow
    Read-Host "按Enter键退出"
}