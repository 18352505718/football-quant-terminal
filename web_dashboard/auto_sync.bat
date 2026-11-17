@echo off
chcp 65001 >nul
title 赛博天眼 · 云端数据自动同步程序
cd /d "%~dp0"
echo 正在启动赛博天眼云端同步引擎...
python sync_to_render.py
if errorlevel 1 (
    echo.
    echo 同步过程中发生错误，请检查网络或 Python 环境。
) else (
    echo.
    echo 同步完成！云端网站已刷新。
)
pause
