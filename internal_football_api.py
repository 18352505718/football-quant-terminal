"""
国内专业足球数据 API 客户端 (Base URL: http://47.99.155.27:8321)
适配 2026-10-28 官方接口清单规范，完整实现：
- 赛程抓取与自动日期格式化 (dd/mm/yyyy 避坑处理)
- 单场全景详情 /match_full 解析 (含 Pinnacle/Bet365/澳盘逐家盘口解析)
- 赛前 xG 预期与近期 xG 形态接入 (/expected_xg, /team_xg_form)
- CLV 赔率走势与冷热资金监控 (/match_clv)
- 历史归档赛程与多公司赔率批量拉取
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, date
from typing import List, Dict, Optional, Any, Union


class FootballAPIClient:
    def __init__(self, token: Optional[str] = None, base_url: str = "http://47.99.155.27:8321"):
        """
        :param token: API Token (优先读取传入的 token，次选 .fdapi_token 文件，再选环境变量 FOOTBALL_API_TOKEN)
        :param base_url: 接口根地址 (默认 http://47.99.155.27:8321)
        """
        self.base_url = base_url.rstrip("/")
        
        # 自动探测 token 文件
        if not token:
            token = os.environ.get("FOOTBALL_API_TOKEN", "")
        if not token:
            local_token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fdapi_token")
            appdata_token_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "opencode-football", ".fdapi_token")
            for p in [local_token_path, appdata_token_path]:
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            t = f.read().strip()
                            if t:
                                token = t
                                break
                    except Exception:
                        pass
        self.token = token or ""

    def _request(self, endpoint: str, params: dict = None, timeout: int = 10) -> Any:
        """底层 HTTP 通信封装，统一挂载 X-API-Token 请求头与异常捕获"""
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"

        if params:
            # 过滤 None 参数并进行 URL 编码
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                url = f"{url}?{urllib.parse.urlencode(clean_params)}"

        headers = {
            "User-Agent": "FootballQuantBot/2.0",
            "Accept": "application/json"
        }
        if self.token:
            headers["X-API-Token"] = self.token

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code == 401:
                raise PermissionError(f"[401 认证失败] API Token 无效或未携带: {err_body} (当前使用 Token: {self.token[:8]}...)")
            raise RuntimeError(f"[HTTP {e.code}] 请求错误 {url}: {err_body}")
        except Exception as e:
            raise ConnectionError(f"[网络连接失败] 无法连接到足球 API 服务 {url}: {e}")

    # ==========================================
    # ① 赛程与今日比赛
    # ==========================================
    def get_today_matches(self) -> Dict[str, Any]:
        """
        获取今起 3 天比赛列表 (/api/today)
        返回字典: count / source / date / odds_coverage / matches[]
        """
        return self._request("api/today")

    def get_matches_by_date(self, query_date: Union[str, date, datetime], limit: int = 500, offset: int = 0, q: str = None) -> Dict[str, Any]:
        """
        按指定日期查询赛程列表 (/matches)
        注意：官方接口严格要求日期格式为 dd/mm/yyyy，传入 YYYY-MM-DD 会被自动纠正为 dd/mm/yyyy 避免静默返回 count=0
        """
        if isinstance(query_date, (date, datetime)):
            formatted_date = query_date.strftime("%d/%m/%Y")
        elif isinstance(query_date, str):
            # 若用户传入形如 2026-11-03 则转为 03/11/2026
            if "-" in query_date:
                parts = query_date.split("-")
                if len(parts) == 3 and len(parts[0]) == 4:
                    formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                else:
                    formatted_date = query_date
            else:
                formatted_date = query_date
        else:
            formatted_date = str(query_date)

        params = {"date": formatted_date, "limit": limit, "offset": offset, "q": q}
        return self._request("matches", params=params)

    def search_matches(self, keyword: str) -> Dict[str, Any]:
        """按队名关键词快速检索近期比赛 (/search?q=)"""
        return self._request("search", params={"q": keyword})

    # ==========================================
    # ② 单场详情与逐家盘口 (含 Pinnacle / Bet365 / 澳盘等)
    # ==========================================
    def get_match_full(self, event_id: Union[int, str]) -> Dict[str, Any]:
        """
        获取单场最详尽数据 (/match_full/{id})
        涵盖: 欧赔/亚盘/大小球/BTTS/逐家原生盘口(odds_by_bookmaker)/阵容/伤停/首发 players_detail
        """
        return self._request(f"match_full/{event_id}")

    def extract_clean_odds(self, match_full_resp: dict) -> dict:
        """
        从 /match_full 中提取并标准化主流博彩公司的赔率数据
        优先提取 Pinnacle (平博锐利度基准) 与 Bet365、威廉希尔
        返回结构化字典:
        {
           'pinnacle': {'1x2': [h, d, a], 'ah': {...}, 'ou25': [over, under]},
           'bet365': {'1x2': [h, d, a], ...},
           'consensus_1x2': [h, d, a]  # 综合均指
        }
        """
        odds_by_bm = match_full_resp.get("odds_by_bookmaker") or {}
        extracted = {}

        # 遍历博彩公司白名单
        for bm_key in ["pinnacle", "bet365", "william-hill", "macauslot", "betfair"]:
            if bm_key not in odds_by_bm:
                continue

            bm_data = odds_by_bm[bm_key]
            bm_parsed = {}

            # 1. 胜平负 (1X2)
            if "胜平负" in bm_data:
                sp = bm_data["胜平负"]
                try:
                    h = float(sp.get("主队", 0))
                    d = float(sp.get("平局", 0))
                    a = float(sp.get("客队", 0))
                    if h > 1.0 and d > 1.0 and a > 1.0:
                        bm_parsed["1x2"] = [h, d, a]
                except (ValueError, TypeError):
                    pass

            # 2. 大小球 (Over/Under 2.5)
            ou_key = next((k for k in bm_data.keys() if "大小球(2.5)" in k or "大小球" in k), None)
            if ou_key and isinstance(bm_data[ou_key], dict):
                ou = bm_data[ou_key]
                over_val = next((ou[k] for k in ou if "大" in k), None)
                under_val = next((ou[k] for k in ou if "小" in k), None)
                if over_val and under_val:
                    bm_parsed["ou_25"] = [float(over_val), float(under_val)]

            # 3. 亚盘让球 (解析各种前缀: 主队让球X / 客队受让X / 平手)
            if "亚盘" in bm_data:
                bm_parsed["handicap"] = bm_data["亚盘"]

            if bm_parsed:
                extracted[bm_key] = bm_parsed

        return extracted

    # ==========================================
    # ③ 批量赔率与 CLV 赔率异动监测
    # ==========================================
    def get_odds_multi_batch(self, event_ids: List[Union[int, str]]) -> Dict[str, Any]:
        """批量获取多场比赛赔率 (/odds_multi_batch?ids=1,2,3)"""
        ids_str = ",".join(str(i) for i in event_ids)
        return self._request("odds_multi_batch", params={"ids": ids_str})

    def get_match_clv(self, event_id: Union[int, str]) -> Dict[str, Any]:
        """
        获取赛前赔率走势与资金热度 (Closing Line Value, /match_clv/{id})
        返回: clv{clv_home, clv_draw, clv_away}
        数值为正表示赔率被热钱下打（变热、机构防范），负值表示升水走弱
        """
        return self._request(f"match_clv/{event_id}")

    # ==========================================
    # ④ xG 数据族
    # ==========================================
    def get_team_xg_form(self, team_name_or_id: Union[str, int], n: int = 10) -> Dict[str, Any]:
        """
        获取球队近期 xG 形态 (/team_xg_form/{team}?n=10)
        支持中文队名 (如 '阿森纳') 或 team_id
        返回: xg_for_avg (场均进球期望), xg_against_avg (场均防守丢球期望) 等
        """
        encoded_team = urllib.parse.quote(str(team_name_or_id))
        return self._request(f"team_xg_form/{encoded_team}", params={"n": n})

    def get_expected_xg(self, event_id: Union[int, str]) -> Dict[str, Any]:
        """
        单场赛前 xG 预期 (/expected_xg/{event_id})
        返回双方赛前模型预期进球数: expected_xg{home, away, home_h1, away_h1}
        """
        return self._request(f"expected_xg/{event_id}")

    # ==========================================
    # ⑤ 历史归档赛程库
    # ==========================================
    def get_archive_matches(self, year: int = None, league: str = None, team: str = None, limit: int = 500, offset: int = 0) -> Dict[str, Any]:
        """
        查询 2020 至今的历史赛果归档库 (/archive/matches)
        返回: matches[]{event_id, home_team, away_team, home_score, away_score, event_date, league}
        """
        params = {"year": year, "league": league, "team": team, "limit": limit, "offset": offset}
        return self._request("archive/matches", params=params)
