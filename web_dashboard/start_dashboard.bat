@echo off
chcp 65001 >nul
title 赛博天眼 · 黑核全维智算矩阵 (CYBER-EYE QUANTUM TERMINAL)
echo =========================================================================
echo   🚀 [CYBER-EYE] 赛博天眼 · 黑核全维智算矩阵 v5.0 已启动！
echo   -----------------------------------------------------------------------
echo   ⭐ 手机/外网专属永久固定网址: https://precision-vividly-monorail.ngrok-free.dev
echo   ⚡ 备用极速直连通道:        https://context-inches-studio-checks.trycloudflare.com
echo   📶 同 Wi-Fi 局域网访问:     http://10.0.0.110:8888
echo   💻 电脑本机访问:            http://127.0.0.1:8888
echo =========================================================================

:: 启动后台 Ngrok 固定域名守护
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
start /B "" "%~dp0ngrok.exe" http --url=precision-vividly-monorail.ngrok-free.dev 8888 >nul 2>&1

:: 启动后台 Cloudflare 极速隧道
start /B "" "%~dp0cloudflared.exe" tunnel --protocol http2 --url http://127.0.0.1:8888 >nul 2>&1

:: 打开电脑浏览器
start http://127.0.0.1:8888

:: 启动核心 Web 智算服务
python "%~dp0server.py" 8888
pause
