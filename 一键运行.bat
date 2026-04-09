@echo off
chcp 65001 >nul
pushd "%~dp0"
setlocal enabledelayedexpansion

REM ---- 默认设置 ----
set "DO_TUNNEL=1"
set "DO_COMBINED=1"
set "DO_SERVICE=1"
set "USE_VENV=1"
set "CLOUDFLARED=cloudflared"
set "CLOUDFLARED_CONFIG=%~dp0\.cloudflared\config.yml"
set "VENV_PY=%~dp0venv\Scripts\python.exe"
if exist "%VENV_PY%" (set "VENV_AVAILABLE=1") else (set "VENV_AVAILABLE=0")
set "PY="

REM ---- 解析参数（省略，与原脚本相同）----
:parse_args
...（保持原样）
:args_done

if "%PY%"=="" (
    if "%USE_VENV%"=="1" if "%VENV_AVAILABLE%"=="1" (
        set "PY=%VENV_PY%"
    ) else (
        set "PY=python"
    )
)

echo 使用 Python: %PY%
echo Cloudflared 可执行: %CLOUDFLARED%
echo Cloudflared 配置: %CLOUDFLARED_CONFIG%
echo 启动项: Tunnel=%DO_TUNNEL% Combined=%DO_COMBINED% Service=%DO_SERVICE%

REM ---- 存储所有子进程的 PID ----
set "PID_FILE=%TEMP%\my_services_pids.txt"
if exist "%PID_FILE%" del "%PID_FILE%"

REM ---- 启动隧道（不创建新窗口，便于管理）----
if "%DO_TUNNEL%"=="1" (
    echo 启动 cloudflared 隧道...
    start /b "%CLOUDFLARED%" --config "%CLOUDFLARED_CONFIG%" tunnel --loglevel info run ai-law-tunnel >nul 2>&1
    for /f "tokens=2" %%a in ('tasklist /fi "imagename eq %CLOUDFLARED%" /fo csv /nh 2^>nul') do (
        set "pid=%%~a"
        echo !pid! >> "%PID_FILE%"
    )
)

if "%DO_COMBINED%"=="1" (
    echo 启动 Combined_server...
    start /b "%PY%" "%~dp0聊天和用户后端\Combined_server.py" >nul 2>&1
    for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
        set "pid=%%~a"
        echo !pid! >> "%PID_FILE%"
    )
)

if "%DO_SERVICE%"=="1" (
    echo 启动 服务.py...
    start /b "%PY%" "%~dp0服务.py" >nul 2>&1
    for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
        set "pid=%%~a"
        echo !pid! >> "%PID_FILE%"
    )
)

echo.
echo 所有服务已启动。按任意键停止所有服务并退出...
pause >nul

REM ---- 停止所有子进程 ----
if exist "%PID_FILE%" (
    for /f %%p in ('type "%PID_FILE%"') do (
        taskkill /pid %%p /f >nul 2>&1
    )
    del "%PID_FILE%"
)

echo 所有服务已停止。
popd
endlocal
goto :eof  