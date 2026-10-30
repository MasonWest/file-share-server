# -*- coding: utf-8 -*-
"""file-share-server 回归测试。

直接跑：`python test_filesvc.py`

不依赖 pytest —— 这个项目的原则是「装完 requirements 就能验证」。
测试全程使用临时目录，不会碰真实 SHARE_DIR。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

SHARE_TMP = tempfile.mkdtemp(prefix="fs_share_")
STATE_TMP = tempfile.mkdtemp(prefix="fs_state_")

# 必须在 import filesvc_api 之前设置：配置在模块导入时读取
os.environ.update(
    {
        "SHARE_DIR": SHARE_TMP,
        "ADMIN_TOKEN": "test-passphrase-2026",
        "PUBLIC_BASE_URL": "http://127.0.0.1:9900",
        "VCLIP_API_URL": "",
        "DEVICES_FILE": str(Path(STATE_TMP) / "devices.json"),
        "SHARES_FILE": str(Path(STATE_TMP) / "shares.json"),
        "LOGIN_MAX_ATTEMPTS": "3",
        "LOGIN_LOCKOUT_SECONDS": "2",
        "LOGIN_LOCKOUT_MAX_SECONDS": "8",
    }
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import filesvc_api as svc  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ADMIN = {"X-Admin-Token": "test-passphrase-2026"}
PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def check(name: str, condition: bool, note: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append((name, note))
        print(f"  FAIL  {name}" + (f"  <- {note}" if note else ""))


def client(ip: str = "10.0.0.1") -> TestClient:
    return TestClient(svc.app_internal, raise_server_exceptions=False, client=(ip, 40000))


def public_client() -> TestClient:
    return TestClient(svc.app_public, raise_server_exceptions=False)


def reset_lock() -> None:
    with svc.admin_login_state_lock:
        svc.admin_login_state.clear()


def main() -> int:
    share = Path(SHARE_TMP)
    (share / "hello.txt").write_text("hello world", encoding="utf-8")
    (share / "sub").mkdir(exist_ok=True)
    (share / "sub" / "inner.txt").write_text("inner", encoding="utf-8")

    c = client()

    print("\n[接口面]")
    check("管理端 /docs 已关闭", c.get("/docs").status_code == 404, f"实际 {c.get('/docs').status_code}")
    check("管理端 /openapi.json 已关闭", c.get("/openapi.json").status_code == 404)
    health = c.get("/health")
    check(
        "/health 返回 ok",
        health.status_code == 200 and health.json().get("status") == "ok",
        str(health.status_code),
    )
    check("/health 泄露版本与分享数", "version" in health.json() and "active_shares" in health.json())
    check(
        "公网端 /health 放行",
        public_client().get("/health").status_code == 200,
    )
    check(
        "公网端其他路径仍 403",
        public_client().get("/api/list").status_code == 403,
    )

    print("\n[鉴权]")
    check("无凭据访问 /api/list 返回 401", c.get("/api/list").status_code == 401)
    check("管理员口令可用", c.get("/api/list", headers=ADMIN).status_code == 200)

    login = c.post("/api/auth/login", json={"token": "test-passphrase-2026", "remember": True})
    body = login.json()
    check("登录成功", login.status_code == 200 and body.get("ok") is True)
    device_token = body.get("device_token")
    device_id = body.get("device_id")
    check("登录返回设备令牌", bool(device_token) and bool(device_id))
    check("登录返回设备名", bool(body.get("device_name")), str(body.get("device_name")))

    dt_headers = {"X-Device-Token": device_token}
    check("设备令牌可访问接口", c.get("/api/list", headers=dt_headers).status_code == 200)
    check(
        "错误设备令牌被拒",
        c.get("/api/list", headers={"X-Device-Token": "bogus"}).status_code == 401,
    )
    check("登录不勾记住则不签发令牌",
         c.post("/api/auth/login", json={"token": "test-passphrase-2026", "remember": False}).json().get("device_token") is None)

    devices_file = Path(STATE_TMP) / "devices.json"
    raw = devices_file.read_text(encoding="utf-8")
    check("devices.json 不落明文令牌", device_token not in raw)
    check("devices.json 存的是哈希", json.loads(raw)[device_id]["hash"] != device_token)

    listing = c.get("/api/devices", headers=dt_headers).json()
    check("设备列表可读取", any(d["id"] == device_id for d in listing.get("devices", [])))

    print("\n[文件操作]")
    check(
        "路径穿越被拒",
        c.get("/api/list/../../Windows", headers=ADMIN).status_code in (400, 404),
    )
    check(
        "绝对路径被拒",
        c.get("/api/download/C:%5CWindows%5Cwin.ini", headers=ADMIN).status_code == 400,
    )
    check(
        "上传正常文件",
        c.post("/api/upload", headers=ADMIN, files={"file": ("up.txt", b"abc", "text/plain")}).status_code == 200,
    )
    check(
        "重名且未开覆盖被拒",
        c.post("/api/upload", headers=ADMIN, files={"file": ("up.txt", b"abc", "text/plain")}).status_code == 400,
    )

    if os.name == "nt":
        bad = c.post(
            "/api/upload",
            headers=ADMIN,
            files={"file": ("bad<name>.txt", b"x", "text/plain")},
        )
        check("非法文件名返回 400 而非 500", bad.status_code == 400, f"实际 {bad.status_code}")
        check("非法文件名不留下残文件", not list(share.glob("bad*")))

    dl = c.get("/api/download/hello.txt", headers=ADMIN)
    check("下载内容一致", dl.status_code == 200 and dl.content == b"hello world")
    check("支持 Range 断点续传", c.get("/api/download/hello.txt", headers={**ADMIN, "Range": "bytes=0-4"}).status_code == 206)
    check("设备令牌可用于下载（查询参数）", c.get(f"/api/download/hello.txt?dt={device_token}").status_code == 200)

    print("\n[分享链接]")
    pub = public_client()
    share_resp = c.post(
        "/api/share-link",
        headers=ADMIN,
        json={"filepath": "hello.txt", "expire_seconds": 60, "max_downloads": 2},
    )
    token = share_resp.json().get("token")
    check("生成分享链接", share_resp.status_code == 200 and bool(token))
    check("公网端凭 token 下载", pub.get(f"/s/{token}").status_code == 200)

    counters = {s["token"]: s for s in c.get("/api/shares", headers=ADMIN).json()}
    check("下载计数 +1", counters[token]["download_count"] == 1)
    pub.get(f"/s/{token}")
    check("超过次数上限后失效", pub.get(f"/s/{token}").status_code == 404)

    # 文件被删除时不应消耗额度（旧实现会先 +1 再校验）
    c.post("/api/upload", headers=ADMIN, files={"file": ("temp.txt", b"temp", "text/plain")})
    ghost = c.post(
        "/api/share-link",
        headers=ADMIN,
        json={"filepath": "temp.txt", "expire_seconds": 60, "max_downloads": 5},
    ).json()["token"]
    (share / "temp.txt").unlink()
    check("文件已删除时返回 404", pub.get(f"/s/{ghost}").status_code == 404)
    ghost_state = {s["token"]: s for s in c.get("/api/shares", headers=ADMIN).json()}
    check(
        "文件已删除时不消耗下载额度",
        ghost_state.get(ghost, {}).get("download_count", 0) == 0,
        f"实际 count={ghost_state.get(ghost, {}).get('download_count')}",
    )

    print("\n[渐进式锁定]")
    reset_lock()
    attacker = client("10.9.9.9")
    codes = [attacker.post("/api/auth/login", json={"token": "wrong"}).status_code for _ in range(3)]
    check("失败 3 次后进入锁定", codes[-1] == 423, f"序列 {codes}")
    locked = attacker.post("/api/auth/login", json={"token": "test-passphrase-2026"})
    check("锁定期间正确口令也被拒", locked.status_code == 423)
    check("锁定响应带 Retry-After 头", locked.headers.get("retry-after") is not None)
    check("锁定响应中文可读", "分钟" in locked.json().get("detail", ""), locked.json().get("detail", ""))

    # 解锁接口：从另一台设备解除
    unlocked = c.post("/api/auth/unlock", headers={**ADMIN}, json={"ip": "10.9.9.9"})
    check("解锁接口清空锁定", unlocked.status_code == 200 and "10.9.9.9" in unlocked.json().get("unlocked", []))
    check("解锁后可正常登录", attacker.post("/api/auth/login", json={"token": "test-passphrase-2026"}).status_code == 200)

    print("\n[设备撤销]")
    revoked = c.delete(f"/api/devices/{device_id}", headers=ADMIN)
    check("撤销设备成功", revoked.status_code == 200)
    check("撤销后该令牌失效", c.get("/api/list", headers=dt_headers).status_code == 401)
    check("撤销不存在的设备返回 404", c.delete("/api/devices/nope", headers=ADMIN).status_code == 404)

    print("\n[分享链接持久化]")
    share_resp = c.post(
        "/api/share-link",
        headers=ADMIN,
        json={"filepath": "hello.txt", "expire_seconds": 600, "max_downloads": 5},
    )
    token = share_resp.json().get("token")
    check("生成分享链接返回 token", bool(token))

    # 模拟重启：新开一个 store 从同一个文件读，等价于进程重启后再加载
    from share_store import ShareStore as _ShareStore

    reloaded = _ShareStore(svc.SHARES_FILE)
    info = reloaded.get(token)
    check("重启后链接仍然存在", info is not None)
    check("持久化的是相对路径", bool(info) and info["filepath"] == "hello.txt", str(info and info["filepath"]))

    reloaded.record_download(token, "10.1.1.1")
    again = _ShareStore(svc.SHARES_FILE).get(token)
    check("下载计数落盘", bool(again) and again["download_count"] == 1, str(again and again["download_count"]))

    revoked_share = c.delete(f"/api/shares/{token}", headers=ADMIN)
    check("作废链接成功", revoked_share.status_code == 200)
    check("作废后公网访问 404", public_client().get(f"/s/{token}").status_code == 404)
    check("作废不存在的链接返回 404", c.delete("/api/shares/nope", headers=ADMIN).status_code == 404)

    print("\n[上传体积上限]")
    original_limit = svc.MAX_UPLOAD_BYTES
    svc.MAX_UPLOAD_BYTES = 16
    big = c.post("/api/upload", headers=ADMIN, files={"file": ("big.bin", b"x" * 4096)})
    check("超限上传返回 413", big.status_code == 413, str(big.status_code))
    check("超限响应说明上限", "上限" in big.json().get("detail", ""), big.json().get("detail", ""))
    check("超限不留下残文件", not (share / "big.bin").exists())
    svc.MAX_UPLOAD_BYTES = original_limit
    ok_upload = c.post("/api/upload", headers=ADMIN, files={"file": ("small.txt", b"ok")})
    check("上限恢复后小文件可上传", ok_upload.status_code == 200, str(ok_upload.status_code))

    print("\n[目录分页]")
    page_dir = share / "many"
    page_dir.mkdir(exist_ok=True)
    for index in range(25):
        (page_dir / f"f{index:02d}.txt").write_text("x", encoding="utf-8")

    first = c.get("/api/list/many?limit=10&offset=0", headers=ADMIN).json()
    check("首页返回 10 条", len(first["files"]) == 10, str(len(first["files"])))
    check("首页标记还有更多", first["has_more"] is True)
    check("总数正确", first["total_files"] == 25, str(first["total_files"]))

    second = c.get("/api/list/many?limit=10&offset=10", headers=ADMIN).json()
    overlap = {item["path"] for item in first["files"]} & {item["path"] for item in second["files"]}
    check("相邻两页不重复", not overlap, str(overlap))

    last_page = c.get("/api/list/many?limit=10&offset=20", headers=ADMIN).json()
    check("末页 5 条且没有更多", len(last_page["files"]) == 5 and last_page["has_more"] is False, str(len(last_page["files"])))

    default_page = c.get("/api/list/many", headers=ADMIN).json()
    check("默认页大小取自配置", default_page["limit"] == svc.DEFAULT_PAGE_SIZE, str(default_page["limit"]))

    everything = c.get("/api/list/many?limit=0", headers=ADMIN).json()
    check("limit=0 返回全量（兼容旧调用）", len(everything["files"]) == 25, str(len(everything["files"])))
    names = [item["name"] for item in everything["files"]]
    check("文件按名称稳定排序", names == sorted(names), str(names[:3]))

    print("\n" + "=" * 52)
    print(f"合计 {len(PASSED) + len(FAILED)} 项：通过 {len(PASSED)}，失败 {len(FAILED)}")
    for name, note in FAILED:
        print(f"  x {name}" + (f"  <- {note}" if note else ""))
    print("=" * 52)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
