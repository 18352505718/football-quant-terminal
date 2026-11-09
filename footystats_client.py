"""
FootyStats API 客户端模块
封装 FootyStats 官方 API，支持拉取真实 xG (预期进球)、历史比赛攻防物理数据以及今日比赛盘口赔率。
具备本地文件缓存机制，防止重复消耗 API 调用额度。
"""

import os
import json
import time
import urllib.request
import urllib.parse
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional


class FootyStatsClient:
    BASE_URL = "https://api.football-data-api.com"

    def __init__(self, api_key: str = "932bc6a4b76c58b53c9caacf87ba2e8cc2750ff7830dca0c4c398d43373d6e60", cache_dir: str = None):
        self.api_key = api_key
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.cache_dir = os.path.join(base_dir, ".cache_footystats")
        else:
            self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

    def _get(self, endpoint: str, params: dict = None, cache_filename: str = None, cache_ttl_sec: int = 43200) -> dict:
        """通用 GET 请求，支持本地缓存 (默认缓存 12 小时)"""
        cache_path = os.path.join(self.cache_dir, cache_filename) if cache_filename else None

        # 检查缓存是否有效
        if cache_path and os.path.exists(cache_path):
            file_age = time.time() - os.path.getmtime(cache_path)
            if file_age < cache_ttl_sec:
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

        # 构造请求 URL
        query_params = {"key": self.api_key}
        if params:
            query_params.update(params)
        url = f"{self.BASE_URL}/{endpoint}?{urllib.parse.urlencode(query_params)}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuantFootballModel/1.0"
        }
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=20) as response:
            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)

        # 写入缓存
        if cache_path and data.get("success", False):
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except Exception:
                pass

        return data

    def get_leagues(self, country: str = None, name_keyword: str = None) -> List[Dict]:
        """获取联赛列表及赛季 ID"""
        cache_file = "league_list.json"
        data = self._get("league-list", cache_filename=cache_file, cache_ttl_sec=86400 * 7)
        leagues = data.get("data", [])

        results = []
        for l in leagues:
            if country and country.lower() not in l.get("country", "").lower():
                continue
            if name_keyword and name_keyword.lower() not in l.get("name", "").lower():
                continue
            results.append({
                "country": l.get("country"),
                "name": l.get("name"),
                "seasons": l.get("season", [])
            })
        return results

    def get_season_matches_df(self, season_id: int, use_cache: bool = True) -> pd.DataFrame:
        """
        拉取某联赛赛季全量比赛，清洗返回包含真实 xG 数据的 DataFrame
        :param season_id: FootyStats 赛季 ID (如英超 2024/2025 赛季为 12325)
        :return: DataFrame，包含 home_team, away_team, home_goals, away_goals, home_xg, away_xg, days_ago 等
        """
        cache_file = f"season_{season_id}_matches.json" if use_cache else None
        data = self._get("league-matches", params={"season_id": season_id}, cache_filename=cache_file, cache_ttl_sec=3600 * 6)
        matches = data.get("data", [])

        now_ts = time.time()
        records = []
        for m in matches:
            # 仅采用已完赛场次
            if m.get("status") != "complete":
                continue

            # 提取真实 xG 与 实际进球
            home_xg = float(m.get("team_a_xg", -1))
            away_xg = float(m.get("team_b_xg", -1))
            home_goals = int(m.get("homeGoalCount", 0))
            away_goals = int(m.get("awayGoalCount", 0))

            # 若该比赛没有 xG 数据 (部分低级别联赛)，回退到真实进球
            if home_xg < 0:
                home_xg = float(home_goals)
            if away_xg < 0:
                away_xg = float(away_goals)

            match_ts = float(m.get("date_unix", now_ts))
            days_ago = max(0.0, (now_ts - match_ts) / 86400.0)

            records.append({
                "date": datetime.fromtimestamp(match_ts).strftime("%Y-%m-%d"),
                "home_team": m.get("home_name", "").strip(),
                "away_team": m.get("away_name", "").strip(),
                "home_goals": home_goals,
                "away_goals": away_goals,
                "home_xg": round(home_xg, 2),
                "away_xg": round(away_xg, 2),
                "days_ago": round(days_ago, 1)
            })

        df = pd.DataFrame(records)
        return df

    def get_todays_matches(self) -> List[Dict]:
        """
        拉取今日比赛列表，包含对阵双方、联赛名、欧赔初指/即时指、赛前 xG 等
        """
        # 今日赛事时效性强，缓存 15 分钟
        data = self._get("todays-matches", cache_filename="todays_matches.json", cache_ttl_sec=900)
        matches = data.get("data", [])

        parsed = []
        for m in matches:
            # 提取 1X2 赔率 (odds_ft_1, odds_ft_x, odds_ft_2)
            try:
                h_odd = float(m.get("odds_ft_1", 0))
                d_odd = float(m.get("odds_ft_x", 0))
                a_odd = float(m.get("odds_ft_2", 0))
            except (ValueError, TypeError):
                h_odd, d_odd, a_odd = 0.0, 0.0, 0.0

            if h_odd <= 1.0 or d_odd <= 1.0 or a_odd <= 1.0:
                continue

            parsed.append({
                "match_id": m.get("id"),
                "competition": m.get("competition_name"),
                "home_team": m.get("home_name", "").strip(),
                "away_team": m.get("away_name", "").strip(),
                "odds_1x2": [h_odd, d_odd, a_odd],
                "status": m.get("status"),
                "time_unix": m.get("date_unix"),
                "home_xg_prematch": float(m.get("team_a_xg_prematch", 0) or 0),
                "away_xg_prematch": float(m.get("team_b_xg_prematch", 0) or 0),
            })
        return parsed
