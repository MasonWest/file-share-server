@echo off
chcp 936 >nul 2>&1
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "ADMIN_PORT=8800"
set "PUBLIC_PORT=9900"
set "FORCE=0"

rem ① 先读 .env 里的真实端口，避免改了配置脚本还去找 8800
if exist ".env" (
    for /f "tokens=2 delims==" %%V in ('findstr /B /I "ADMIN_PORT=" .env 2^>nul') do set "ADMIN_PORT=%%V"
    for /f "tokens=2 delims==" %%V in ('findstr /B /I "PUBLIC_PORT=" .env 2^>nul') do set "PUBLIC_PORT=%%V"
)
rem 去掉值可能带的空格
for /f "tokens=1" %%P in ("!ADMIN_PORT!") do set "ADMIN_PORT=%%P"
for /f "tokens=1" %%P in ("!PUBLIC_PORT!") do set "PUBLIC_PORT=%%P"

rem ② 命令行参数优先于 .env
rem 只有纯数字才当端口。之所以要校验：在 Git Bash / MSYS 里 /force 会被
rem 自动转成 C:/xxx/force 这种路径，不校验的话端口变成一个路径，脚本会
rem 安静地什么都不做——这比报错更难查。
set "ARG1=%~1"
set "ARG2=%~2"
if /i "%ARG1%"=="/force" set "FORCE=1"
if /i "%ARG1%"=="force" set "FORCE=1"

set "NONNUM1="
set "NONNUM2="
if not "%ARG1%"=="" for /f "delims=0123456789" %%X in ("%ARG1%") do set "NONNUM1=1"
if not "%ARG2%"=="" for /f "delims=0123456789" %%X in ("%ARG2%") do set "NONNUM2=1"
if not "%ARG1%"=="" if not defined NONNUM1 set "ADMIN_PORT=%ARG1%"
if not "%ARG2%"=="" if not defined NONNUM2 set "PUBLIC_PORT=%ARG2%"
if defined NONNUM1 if "%FORCE%"=="0" echo [提示] 忽略无法识别的参数: %ARG1%

echo ========================================
echo  File Share Server - 关闭
echo ========================================
echo.
echo 管理端口: !ADMIN_PORT!    公网端口: !PUBLIC_PORT!
echo.

rem ---------------------------------------------------------------- 找监听进程
set "PIDS="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:":!ADMIN_PORT! " ^| findstr /I "LISTENING"') do (
    if not defined SEEN_%%P (
        set "SEEN_%%P=1"
        set "PIDS=!PIDS! %%P"
    )
)

if not defined PIDS (
    echo [信息] 端口 !ADMIN_PORT! 上没有正在监听的服务，可能已经关闭。
    goto :CHECK_PUBLIC
)

for %%P in (!PIDS!) do call :KILL_ONE %%P

:CHECK_PUBLIC
rem 双端口跑在同一个进程里，上面杀掉就一起没了。
rem 这里确认 9900 是否释放，顺便提示「被别的程序占着」这种情况。
set "LEFT="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /C:":!PUBLIC_PORT! " ^| findstr /I "LISTENING"') do set "LEFT=%%P"
if defined LEFT (
    echo [提示] 端口 !PUBLIC_PORT! 仍被 PID !LEFT! 占用，可能不是本服务的进程。
    for /f "tokens=1 delims=," %%N in ('tasklist /fi "PID eq !LEFT!" /fo csv /nh 2^>nul ^| findstr /I ".exe"') do echo        进程名: %%~N
)

echo.
rem ---------------------------------------------------------------- 确认端口已释放
set "STILL=1"
for /l %%I in (1,1,6) do (
    if "!STILL!"=="1" (
        netstat -ano | findstr /C:":!ADMIN_PORT! " | findstr /I "LISTENING" >nul 2>&1
        if errorlevel 1 (
            set "STILL=0"
        ) else (
            ping -n 2 127.0.0.1 >nul
        )
    )
)

if "!STILL!"=="0" (
    echo [完成] 端口 !ADMIN_PORT! 已释放。
) else (
    echo [失败] 端口 !ADMIN_PORT! 仍在监听。
    if "!SKIPPED!"=="1" echo        占用者不是本服务，确认要结束请运行: stop_server.bat /force
    if not "!SKIPPED!"=="1" echo        可能是权限更高的进程，请右键「以管理员身份运行」再试。
)

echo.
pause
exit /b 0

:KILL_ONE
set "TPID=%~1"
set "TNAME="
for /f "tokens=1 delims=," %%N in ('tasklist /fi "PID eq %TPID%" /fo csv /nh 2^>nul ^| findstr /I ".exe"') do set "TNAME=%%~N"
if not defined TNAME (
    echo [跳过] PID %TPID% 已经退出。
    exit /b 0
)

rem 只杀 python 进程。端口被别的程序占着时默认不动手——
rem 「一键关闭」不该顺手杀掉用户没在说的东西。
echo !TNAME! | findstr /I "python" >nul
if errorlevel 1 (
    if "%FORCE%"=="1" (
        echo [强制] 结束 !TNAME! ^(PID %TPID%^)
        taskkill /PID %TPID% /T /F >nul 2>&1
    ) else (
        echo [跳过] 端口被 !TNAME! ^(PID %TPID%^) 占用，不是本服务的进程。
        echo        确认要结束它请运行: stop_server.bat /force
        set "SKIPPED=1"
    )
    exit /b 0
)

echo [关闭] !TNAME! ^(PID %TPID%^)
taskkill /PID %TPID% /T /F >nul 2>&1
if errorlevel 1 (
    echo [失败] 无法结束 PID %TPID%，请以管理员身份重试。
) else (
    echo [成功] 已结束进程 %TPID%。
)
exit /b 0
