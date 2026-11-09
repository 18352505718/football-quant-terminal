"""
赛眼数据 (saiyanshuju.cn) 客户端
支持：
1. 激活码兑换 (action: activation)
2. 账号密码登录 (action: login)
3. 竞彩今日赛程数据获取 (/api/today)
4. xG 预期进球与量化推荐获取 (/api/xg, /api/picks)
5. 自动持久化保存已获取的 Token 到本地
"""

import os
import json
import secrets
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional


class SaiyanShujuClient:
    AUTH_ENDPOINT = "https://flweb-d9garmgie7664b6d2.service.tcloudbase.com/api/redeem"
    API_BASE = "https://flweb-d9garmgie7664b6d2.service.tcloudbase.com/api"

    def __init__(self, token: Optional[str] = None, token_file: str = ".saiyanshuju_token.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.token_file = os.path.join(base_dir, token_file)
        self.device_file = os.path.join(base_dir, ".saiyanshuju_device.json")

        self.device_id = self._load_or_create_device_id()
        self.token = token or self._load_saved_token()

    def _load_or_create_device_id(self) -> str:
        """加载或生成符合赛眼规范的 device_id: d_ + 24位 hex"""
        if os.path.exists(self.device_file):
            try:
                with open(self.device_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("device_id"):
                        return data["device_id"]
            except Exception:
                pass

        dev_id = "d_" + secrets.token_hex(12)
        try:
            with open(self.device_file, "w", encoding="utf-8") as f:
                json.dump({"device_id": dev_id}, f)
        except Exception:
            pass
        return dev_id

    def _load_saved_token(self) -> str:
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("token", "")
            except Exception:
                pass
        return ""

    def save_token(self, token: str, extra_info: dict = None):
        self.token = token
        payload = {"token": token}
        if extra_info:
            payload.update(extra_info)
        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _post_auth(self, action: str, params: dict) -> Dict[str, Any]:
        """向 /api/redeem 发送认证请求"""
        body = {"action": action, "device_id": self.device_id}
        body.update(params)

        req_data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuantModel/1.0",
            "Origin": "https://saiyanshuju.cn",
            "Referer": "https://saiyanshuju.cn/"
        }
        req = urllib.request.Request(self.AUTH_ENDPOINT, data=req_data, headers=headers)

        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def activate_code(self, code: str) -> Dict[str, Any]:
        """使用激活码激活"""
        clean_code = str(code).replace("-", "").strip()
        resp = self._post_auth("activation", {"code": clean_code})

        if resp.get("ok"):
            token = resp.get("token", "")
            if token:
                self.save_token(token, resp)
        return resp

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """使用用户名与密码登录"""
        resp = self._post_auth("login", {"username": username.strip(), "password": password})
        if resp.get("ok"):
            token = resp.get("token", "")
            if token:
                self.save_token(token, resp)
        return resp

    def get_today_matches(self, date_str: str = None) -> Dict[str, Any]:
        """
        拉取赛眼竞彩今日赛程数据 (/api/today)
        支持免费与会员两种模式，若已配置 Token 会自动以 Bearer Token 形式携带
        """
        url = f"{self.API_BASE}/today"
        if date_str:
            url += f"?date={urllib.parse.quote(date_str)}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://saiyanshuju.cn",
            "Referer": "https://saiyanshuju.cn/"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_picks(self) -> Dict[str, Any]:
        """获取赛眼官方模型推荐 (/api/picks)"""
        url = f"{self.API_BASE}/picks"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://saiyanshuju.cn",
            "Referer": "https://saiyanshuju.cn/"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
