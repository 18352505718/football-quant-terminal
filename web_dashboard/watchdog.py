# -*- coding: utf-8 -*-
"""
watchdog.py - 赛博天眼 7x24 小时高可用守护看门狗 (CyberEye High-Availability Watchdog)
彻底脱离 IDE 与 Agent 终端生命周期，常驻 Windows 后台。
每 15 秒双向心跳巡检：
1. 本地 Web 服务 (127.0.0.1:8888) 心跳，挂掉立即 1 秒内重启自愈；
2. 公网隧道 (Ngrok 4040 API) 状态，断开立即自动重连并锁定永久域名；
3. 输出日志至 watchdog.log，全流程透明可追溯。
"""

import os
import sys
import time
import json
import socket
import subprocess
import urllib.request
import datetime as dt

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 单实例独占锁 (Loopback Socket Lock, 端口 18889)
_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_socket.bind(("127.0.0.1", 18889))
except Exception:
    sys.exit(0)

# 启用 Windows 离开模式 (Away Mode) 与防系统休眠：
# 允许显示器黑屏熄灭省电，但保持 CPU、网卡与进程持续运转，支持 7x24h 对外服务
def keep_system_awake():
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_AWAYMODE_REQUIRED = 0x00000040
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
    except Exception:
        pass

keep_system_awake()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
NGROK_BAT = os.path.join(BASE_DIR, "run_ngrok_fixed.bat")
LOG_PATH = os.path.join(BASE_DIR, "watchdog.log")

PYTHON_EXE = sys.executable

def log(msg):
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line)
    except Exception:
        pass

def check_port_open(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

def check_server_alive():
    if not check_port_open(8888):
        return False
    try:
        req = urllib.request.Request("http://127.0.0.1:8888/api/data")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return check_port_open(8888)

def check_ngrok_alive():
    if not check_port_open(4040):
        return False
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                tunnels = data.get("tunnels", [])
                for t in tunnels:
                    if "precision-vividly-monorail" in t.get("public_url", ""):
                        return True
        return False
    except Exception:
        return check_port_open(4040)

def kill_process_on_port(port):
    try:
        cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
    except Exception as e:
        log(f"清理端口 {port} 进程异常: {e}")

def kill_ngrok_processes():
    try:
        subprocess.run("taskkill /F /IM ngrok.exe /T", shell=True, capture_output=True, timeout=5)
    except Exception:
        pass

def launch_server():
    log("[WARN] 监测到 Web 服务掉线，正在执行一键自愈重启...")
    kill_process_on_port(8888)
    time.sleep(1)
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    
    cmd = [PYTHON_EXE, SERVER_SCRIPT, "8888"]
    subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    log("[INFO] Web 服务已成功拉起 (端口: 8888)")

def launch_ngrok():
    log("[WARN] 监测到 Ngrok 公网隧道掉线，正在重新建立隧道...")
    kill_ngrok_processes()
    time.sleep(1)
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    cmd = ["cmd.exe", "/c", NGROK_BAT]
    subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    log("[INFO] Ngrok 隧道已成功拉起，重新绑定: precision-vividly-monorail.ngrok-free.dev")

def main_loop():
    log("[START] 赛博天眼看门狗 (CyberEye Watchdog) 正式启动！进入 7x24h 自愈巡检模式...")
    
    # 启动时初检
    if not check_server_alive():
        launch_server()
        time.sleep(3)
    else:
        log("[OK] Web 服务处于正常运行状态")

    if not check_ngrok_alive():
        launch_ngrok()
        time.sleep(3)
    else:
        log("[OK] Ngrok 公网隧道处于正常运行状态")

    consecutive_server_fails = 0
    consecutive_ngrok_fails = 0

    while True:
        try:
            keep_system_awake()
            # 1. 检查 Web 服务
            if not check_server_alive():
                consecutive_server_fails += 1
                log(f"[WARN] Web 服务连续心跳失败次数: {consecutive_server_fails}")
                if consecutive_server_fails >= 2:
                    launch_server()
                    consecutive_server_fails = 0
                    time.sleep(2)
            else:
                consecutive_server_fails = 0

            # 2. 检查 Ngrok 隧道
            if not check_ngrok_alive():
                consecutive_ngrok_fails += 1
                log(f"[WARN] Ngrok 隧道连续心跳失败次数: {consecutive_ngrok_fails}")
                if consecutive_ngrok_fails >= 2:
                    launch_ngrok()
                    consecutive_ngrok_fails = 0
                    time.sleep(3)
            else:
                consecutive_ngrok_fails = 0

        except Exception as e:
            log(f"[ERROR] 看门狗主循环异常: {e}")

        time.sleep(15)

if __name__ == "__main__":
    main_loop()
