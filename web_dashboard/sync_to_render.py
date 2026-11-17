# -*- coding: utf-8 -*-
"""
赛博天眼 · 云端全自动增量同步脚本 (Sync to Render)
本脚本运行在本地国内网络环境，直连体彩官方网关并完成量化模型计算，
随后通过安全 API 通道将最新数据推送到 Render 云端！
"""
import os
import sys
import json
import urllib.request
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

import daily_updater

RENDER_PUSH_URL = "https://football-quant-terminal.onrender.com/api/push_cache"
SYNC_TOKEN = "cybereye_sync_2026"

def run_sync():
    t0 = time.time()
    print("=" * 65)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 赛博天眼 · 云端数据自动同步开始...")
    print("=" * 65)
    
    # 1. 运行本地日常数据管道（国内直连体彩网关 + 负二项模型推演）
    cache = daily_updater.run_update_now()
    if not cache:
        print("❌ 本地数据处理失败，终止推送")
        return False
        
    match_cnt = len(cache.get("active_matches", []))
    parlay_cnt = len(cache.get("active_parlays", []))
    print(f"✅ 本地计算完毕: 在售比赛 {match_cnt} 场，实战组合 {parlay_cnt} 套")
    
    # 2. 读取并推送到 Render 云端
    cache_path = os.path.join(CURRENT_DIR, "daily_pipeline_cache.json")
    if not os.path.exists(cache_path):
        print("❌ 未找到 daily_pipeline_cache.json")
        return False
        
    with open(cache_path, "rb") as f:
        data = f.read()
        
    req = urllib.request.Request(RENDER_PUSH_URL, data=data, headers={
        "Content-Type": "application/json",
        "X-Sync-Token": SYNC_TOKEN
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            elapsed = round(time.time() - t0, 2)
            print(f"🚀 云端同步成功！Render 响应状态码: {resp.status}，耗时: {elapsed}s")
            print(f"   返回内容: {body}")
            print(f"   访问网址: https://football-quant-terminal.onrender.com/")
            print("=" * 65)
            return True
    except Exception as e:
        print(f"❌ 推送云端失败: {e}")
        print("=" * 65)
        return False

if __name__ == "__main__":
    run_sync()
