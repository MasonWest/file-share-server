# -*- coding: utf-8 -*-
"""分享链接持久化：让链接活过服务重启。

为什么需要它
------------
旧实现把分享 token 全放内存字典里，进程一重启、或者 `start_server.bat` 被
关掉再开，所有已经发出去的链接集体 404。对「把链接丢进群里让朋友下个文件」
这种场景，这是最容易被骂的缺陷。

为什么还是 JSON 而不是 SQLite
----------------------------
这个项目的形态是单人内网工具，活跃分享常年个位数到几十条。为了这点数据引入
SQLite + ORM，换来的是迁移脚本、并发写锁、和「数据库文件放哪」的新问题。
写入走「临时文件 + os.replace」已经能保证崩溃时不会读到半截 JSON。

存的是什么
----------
只存**相对 SHARE_DIR 的路径**，不存绝对路径。这样把 SHARE_DIR 从 F:\\SMB
换到别处、或者整体搬到另一台机器，旧链接照样指得对。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
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


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


class ShareStore:
    """分享 token 的创建 / 查询 / 计数 / 清理。线程安全，进程内单例使用。"""

    def __init__(self, path: Path | str, max_history_per_link: int = 10) -> None:
        self.path = Path(path)
        self.max_history_per_link = max(1, int(max_history_per_link))
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
            # 文件不存在或损坏 → 当成「没有活跃链接」。
            # 坏文件不阻断启动：最坏情况是重新生成链接。
            self._data = {}
        return self._data

    def _flush(self) -> None:
        data = self._data or {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, self.path)

    def _prune(self, data: dict[str, dict], now: datetime) -> bool:
        dead = [
            token
            for token, item in data.items()
            if (_parse_dt(item.get("expires_at")) or now) <= now
        ]
        for token in dead:
            data.pop(token, None)
        return bool(dead)

    # ---------------- 对外接口 ----------------

    def add(
        self,
        token: str,
        filepath: str,
        expires_at: datetime,
        max_downloads: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            data = self._load()
            self._prune(data, now)
            data[token] = {
                "filepath": filepath,
                "created_at": _iso(now),
                "expires_at": _iso(expires_at),
                "max_downloads": int(max_downloads),
                "download_count": 0,
                "downloads": [],
            }
            self._flush()

    def get(self, token: str) -> dict | None:
        """返回链接信息（含剩余额度），过期或不存在返回 None。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            data = self._load()
            pruned = self._prune(data, now)
            item = data.get(token)
            if pruned:
                self._flush()
        if not item:
            return None
        return {
            "filepath": item.get("filepath", ""),
            "expires_at": _parse_dt(item.get("expires_at")),
            "max_downloads": int(item.get("max_downloads", 0)),
            "download_count": int(item.get("download_count", 0)),
            "downloads": list(item.get("downloads", [])),
        }

    def record_download(self, token: str, client_ip: str) -> dict | None:
        """原子地 +1 一次计数。链接已失效/超额则返回 None。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            data = self._load()
            self._prune(data, now)
            item = data.get(token)
            if not item:
                self._flush()
                return None
            if int(item.get("download_count", 0)) >= int(item.get("max_downloads", 0)):
                data.pop(token, None)
                self._flush()
                return None
            item["download_count"] = int(item.get("download_count", 0)) + 1
            history = list(item.get("downloads", []))
            history.append({"ip": client_ip, "time": _iso(now)})
            item["downloads"] = history[-self.max_history_per_link :]
            self._flush()
            return {
                "download_count": item["download_count"],
                "max_downloads": int(item.get("max_downloads", 0)),
            }

    def remove(self, token: str) -> bool:
        with self._lock:
            data = self._load()
            if token not in data:
                return False
            data.pop(token, None)
            self._flush()
            return True

    def purge_expired(self, now: datetime | None = None) -> list[str]:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            data = self._load()
            expired = [
                token
                for token, item in data.items()
                if (_parse_dt(item.get("expires_at")) or current) <= current
            ]
            for token in expired:
                data.pop(token, None)
            if expired:
                self._flush()
        return expired

    def list_all(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        with self._lock:
            data = self._load()
            if self._prune(data, now):
                self._flush()
            items = [
                {
                    "token": token,
                    "filepath": str(item.get("filepath", "")),
                    "created_at": item.get("created_at"),
                    "expires_at": item.get("expires_at"),
                    "max_downloads": int(item.get("max_downloads", 0)),
                    "download_count": int(item.get("download_count", 0)),
                    "downloads": list(item.get("downloads", [])),
                }
                for token, item in data.items()
            ]
        return sorted(items, key=lambda i: str(i.get("created_at") or ""), reverse=True)

    def count(self) -> int:
        with self._lock:
            return len(self._load())
