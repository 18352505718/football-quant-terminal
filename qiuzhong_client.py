"""
球中 API (https://qiuzhong.fastoffice.site/v1) 客户端
严格遵循 qiuzhong-api-client Skill 规范：
1. 请求头携带 X-Api-Key
2. 首次/查验配额调用 /v1/usage
3. 频率限制控制 (<= 50次/分钟)
4. 支持竞彩足球奖金、赛前 xG、多机构盘口快照、资金分布与变盘历史
"""

import time
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, List


class QiuZhongClient:
    BASE_URL = "https://qiuzhong.fastoffice.site/v1"

    def __init__(self, api_key: str = "qz_key_Oe122O8voTIpZCO3HfQp3SwULUastcbaz8LeVZlWbLg"):
        self.api_key = api_key
        self.usage_cache = None

    def _request(self, endpoint: str, params: dict = None, retries: int = 2) -> Dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        url = f"{self.BASE_URL}/{endpoint}"
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                url += f"?{urllib.parse.urlencode(clean_params)}"

        headers = {
            "X-Api-Key": self.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuantFootballModel/1.0",
            "Accept": "application/json"
        }

        last_err = None
        for attempt in range(retries + 1):
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                if e.code == 429:
                    retry_after = int(e.headers.get("Retry-After", 2))
                    time.sleep(retry_after)
                    continue
                elif e.code == 503 and attempt < retries:
                    time.sleep(1.5)
                    continue
                raise RuntimeError(f"[HTTP {e.code}] {url}: {err_body}")
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(1.0)
                    continue
                raise ConnectionError(f"请求球中 API 失败 ({url}): {last_err}")

    def get_usage(self) -> Dict[str, Any]:
        """查询当前 Key 的套餐、额度与频率限制 (/usage)"""
        data = self._request("usage")
        self.usage_cache = data
        return data

    def get_bookmakers(self) -> List[Dict[str, Any]]:
        """获取支持的博彩公司清单 (/bookmakers)"""
        data = self._request("bookmakers")
        return data.get("数据", [])

    def get_jc_matches(self, date_str: str) -> Dict[str, Any]:
        """获取指定日期竞彩足球赛程与五种最新奖金 (/jc/matches?date=YYYY-MM-DD)"""
        return self._request("jc/matches", params={"date": date_str})

    def get_match_prematch_xg(self, match_id: str) -> Dict[str, Any]:
        """获取单场赛前物理 xG 预期 (/matches/{matchId}/prematch-xg)"""
        return self._request(f"matches/{match_id}/prematch-xg")

    def get_match_odds(self, match_id: str, bookmaker_ids: str = None) -> Dict[str, Any]:
        """获取单场赛前盘口快照 (/matches/{matchId}/odds)"""
        params = {"bookmaker_ids": bookmaker_ids} if bookmaker_ids else None
        return self._request(f"matches/{match_id}/odds", params=params)

    def get_match_money(self, match_id: str) -> Dict[str, Any]:
        """获取单场资金分布与热度成交 (/matches/{matchId}/money)"""
        return self._request(f"matches/{match_id}/money")
