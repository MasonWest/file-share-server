# -*- coding: utf-8 -*-
"""设备信任令牌：登录一次，之后免密。

为什么这么设计
--------------
这是个私人内网工具，用户要在手机、平板、VR 头显、办公电脑上来回登录。
32 位随机管理员口令在数学上漂亮，在人类身上不成立——记不住的东西最后会被
写在便签上、存进聊天记录里，安全性反而归零。

所以把「记忆成本」从人转移到设备：
- 管理口令只在新设备首次登录时输入一次，可以继续用自己好记的
- 登录成功后签发设备令牌，长期有效，前端存 localStorage
- 令牌在服务端只存 sha256 哈希，文件泄露也无法直接冒用
- 每台设备可单独撤销，丢一台不影响其他

存储用 JSON 而不是数据库：这个项目的原则是零持久化依赖，为了 5 条设备记录
引入 SQLite 甚至 ORM 是负收益。写入走「临时文件 + os.replace」保证原子性。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class DeviceStore:
    """设备令牌的签发 / 校验 / 撤销。线程安全，进程内单例使用。"""

    def __init__(self, path: Path | str, ttl_days: int = 365) -> None:
        self.path = Path(path)
        self.ttl_days = max(1, int(ttl_days))
        self._lock = Lock()
        self._data: dict[str, dict] | None = None

    # ---------------- 内部：读写 ----------------

    def _load(self) -> dict[str, dict]:
        if self._data is not None:
            return self._data
        try:
            raw = json.loads(self.path.read_text("utf-8"))
            self._data = raw if isinstance(raw, dict) else {}
        except (FileNotFoundError, ValueError):
            # 文件不存在或内容损坏，一律当成「还没有任何受信设备」
            # 坏文件不阻断启动：最坏情况是所有人重登一次
            self._data = {}
        return self._data

    def _flush(self) -> None:
        data = self._data or {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, self.path)

    def _prune(self, data: dict[str, dict]) -> bool:
        """清掉已过期的设备记录，返回是否有改动。"""
        now = datetime.now(timezone.utc)
        dead = [key for key, item in data.items() if (_parse_dt(item.get("expires_at")) or now) <= now]
        for key in dead:
            data.pop(key, None)
        return bool(dead)

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    # ---------------- 对外接口 ----------------

    def issue(self, name: str) -> tuple[str, str, str]:
        """签发一台新设备。返回 (设备令牌, 设备ID, 过期时间ISO)。

        明文令牌只在此刻返回一次，之后服务端只有哈希。
        """
        token = secrets.token_urlsafe(32)
        device_id = secrets.token_hex(4)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self.ttl_days)

        with self._lock:
            data = self._load()
            self._prune(data)
            data[device_id] = {
                "name": (name or "未命名设备")[:60],
                "hash": self._hash(token),
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
            self._flush()

        return token, device_id, expires_at.isoformat()

    def verify(self, token: str | None) -> bool:
        if not token:
            return False
        digest = self._hash(token)
        now = datetime.now(timezone.utc)

        with self._lock:
            data = self._load()
            pruned = self._prune(data)
            hit = False
            for item in data.values():
                if not hmac.compare_digest(str(item.get("hash", "")), digest):
                    continue
                expires_at = _parse_dt(item.get("expires_at"))
                if expires_at is not None and expires_at <= now:
                    continue
                hit = True
                break
            if pruned:
                self._flush()

        return hit

    def list_devices(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        with self._lock:
            data = self._load()
            if self._prune(data):
                self._flush()
            devices = [
                {
                    "id": key,
                    "name": str(item.get("name", "未命名设备")),
                    "created_at": item.get("created_at"),
                    "expires_at": item.get("expires_at"),
                    "expired": (_parse_dt(item.get("expires_at")) or now) <= now,
                }
                for key, item in data.items()
            ]
        return sorted(devices, key=lambda d: str(d.get("created_at") or ""), reverse=True)

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            data = self._load()
            if device_id not in data:
                return False
            data.pop(device_id, None)
            self._flush()
            return True
