@echo off
chcp 65001 >nul
title 图书馆座位预约系统

echo ========================================
echo   图书馆座位预约系统 - 启动中...
echo ========================================

:: 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行: python -m venv .venv
    pause
    exit /b 1
)

:: 检查 .env
if not exist ".env" (
    echo [错误] 未找到 .env 配置文件
    echo 请从 .env.example 复制并填写 API key
    pause
    exit /b 1
)

echo [信息] 启动服务器 (http://localhost:8000)
.venv\Scripts\python.exe -m api.server

pause
