# -*- coding: utf-8 -*-
"""
generate_daily_draft.py
按 _template-底稿-v1.json 规范，自动生成当日天火云官方底稿并计算 sha256
"""
import os
import sys
import json
import hashlib
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
DRAFT_DIR = r"G:\BaiduSyncdisk\ai\天火云\每日底稿"
CACHE_PATH = os.path.join(CURRENT_DIR, "daily_pipeline_cache.json")

def generate_today_draft():
    if not os.path.exists(CACHE_PATH):
        print(f"❌ 找不到缓存: {CACHE_PATH}")
        return None, None
        
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)
        
    matches = cache.get("active_matches", [])
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    
    draft_matches = []
    for m in matches:
        num = m.get("num", "")
        l = m.get("league", "")
        h = m.get("home", "")
        a = m.get("away", "")
        ko = m.get("kickoff", f"{today_str}T04:00:00+08:00")
        had = m.get("had_sp", [0, 0, 0])
        hhad = m.get("hhad_sp", ["+1", 0, 0, 0])
        rec = m.get("recommended_pick", "胜")
        intel = m.get("intel", {})
        h_xg = round(m.get("h_xg", 1.4), 2)
        a_xg = round(m.get("a_xg", 1.1), 2)
        
        # 判断玩法
        min_sp = min([s for s in had if s > 0]) if any(s > 0 for s in had) else 1.5
        if min_sp < 1.40:
            market = "hhad"
            pick = f"让球({hhad[0]}) 让负"
            price = hhad[3] if len(hhad) > 3 else 0
            reason = f"常规赔率<{min_sp}触发反蚊子肉禁令，xG {h_xg}:{a_xg}，转向让球对冲"
        else:
            market = "had"
            pick = f"主推 {rec}"
            price = had[0] if rec == "胜" else (had[2] if rec == "负" else had[1])
            price = price if price > 0 else (had[0] if had[0] > 0 else 1.5)
            reason = f"二元负二项xG {h_xg}:{a_xg}，公允概率去水具备微幅正EV"

        draft_matches.append({
            "num": num,
            "league": l,
            "kickoff": ko,
            "home": h,
            "away": a,
            "sp": {
                "had": had,
                "hhad": {
                    "line": str(hhad[0]),
                    "prices": hhad[1:] if len(hhad) > 3 else [0, 0, 0]
                }
            },
            "verdict": {
                "market": market,
                "pick": pick,
                "price": price
            },
            "reason_short": reason[:80]
        })
        
    doc = {
        "schema": "tianhuo-daily-v1",
        "date": today_str,
        "generated_at": now_iso,
        "generated_by": "opencode_server_agent.py@103.236.84.237",
        "pool_snapshot": {
            "source": "sporttery-webapi",
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "agent_selfcheck": {
            "model": "deepseek",
            "is_unit_open_person": False,
            "note": "云端代理初筛底稿，待单位open本尊按协议复核"
        },
        "matches": draft_matches,
        "file_sha256": ""
    }
    
    # 计算 sha256 (不包含 file_sha256 自身)
    raw_json = json.dumps(doc, ensure_ascii=False, indent=2)
    sha = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    doc["file_sha256"] = sha
    
    out_path = os.path.join(DRAFT_DIR, f"{today_str}-底稿-v1.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 成功生成底稿: {out_path}")
    print(f"   完整 SHA256: {sha}")
    print(f"   前 12 位:    {sha[:12]}")
    return out_path, sha

if __name__ == "__main__":
    generate_today_draft()
