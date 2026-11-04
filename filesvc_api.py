# -*- coding: utf-8 -*-
"""私人文件分享服务。

两个 FastAPI 实例跑在同一进程的两个端口上：
- 管理端（默认 8800）：内网访问，浏览 / 上传 / 下载 / 生成分享链接
- 公网端（默认 9900）：只有 /s/{token} 一条路由，其余一律 403

认证模型
--------
1. 管理口令（ADMIN_TOKEN）：只在新设备首次登录时输入一次，可以用好记的。
2. 设备令牌（device token）：登录成功后签发，长期有效、可单独撤销。
   前端存 localStorage，之后所有请求用它，口令不再落盘。

   这么设计是因为使用者要在手机 / 平板 / VR 头显之间来回登录，长随机口令
   在现实中会被写在便签上。强度靠「设备令牌 + 渐进式锁定」承担，而不是靠
   逼人背一串 43 位的字符串。
"""

from __future__ import annotations

import base64
import hmac
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_hex
from threading import Lock
from typing import Dict
from urllib import error as urlerror
from urllib import request as urlrequest

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from device_store import DeviceStore
from share_store import ShareStore

# 二维码是可选能力：没装 qrcode 时只有「创建分享」抽屉里的扫码区降级成链接框，
# 其余功能一概不受影响。做成可选是为了不让 pip 少装一个包就把整个服务拖挂。
try:
    import qrcode
    import qrcode.image.svg as qr_svg
except ImportError:  # pragma: no cover - 取决于部署环境
    qrcode = None
    qr_svg = None

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("filesvc")
# httpx 会把每一次内部请求都写成 INFO，日常日志里全是噪音
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ---------------------------------------------------------------- 配置
PROJECT_DIR = Path(__file__).resolve().parent

SHARE_DIR = os.getenv("SHARE_DIR", "shared")
BASE_DIR = Path(SHARE_DIR).resolve()
BASE_DIR.mkdir(exist_ok=True, parents=True)

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN") or os.getenv("admin_token")
if not ADMIN_TOKEN:
    raise RuntimeError("ADMIN_TOKEN/admin_token is required.")

# 管理端默认监听所有网卡：使用场景是「手机 / 平板 / VR 都要从内网登录」。
# 安全边界不在绑定地址上，而在两处：路由器只映射公网端端口 + 设备令牌鉴权。
ADMIN_HOST = os.getenv("ADMIN_HOST", "0.0.0.0")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8800"))
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "0.0.0.0")
PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", "9900"))
ALLOW_OVERWRITE = os.getenv("ALLOW_OVERWRITE", "false").lower() == "true"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:9900").rstrip("/")
DEFAULT_TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))
DEFAULT_SHARE_EXPIRE_SECONDS = DEFAULT_TOKEN_EXPIRE_HOURS * 3600
MAX_SHARE_EXPIRE_SECONDS = 7 * 24 * 3600
MAX_DOWNLOADS = int(os.getenv("MAX_DOWNLOADS", "100"))

# 设备令牌
DEVICE_TOKEN_TTL_DAYS = int(os.getenv("DEVICE_TOKEN_TTL_DAYS", "365"))
DEVICES_FILE = Path(os.getenv("DEVICES_FILE", PROJECT_DIR / "devices.json"))

# 分享链接持久化：重启不再是「所有链接失效」。
# 只存相对 SHARE_DIR 的路径，换盘 / 换机器后旧链接依然有效。
SHARES_FILE = Path(os.getenv("SHARES_FILE", PROJECT_DIR / "shares.json"))
share_store = ShareStore(SHARES_FILE)

# 上传体积上限（MB），0 表示不限制。
# 私人服务里一个误拖的 80GB 镜像能把连接占满半天，默认给 4GB 兜底。
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "4096"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024 if MAX_UPLOAD_MB > 0 else 0

# 目录分页：私人目录动辄几千个文件，一次全量返回既慢又占内存。
# 默认每页 200 条，前端点「加载更多」累计；limit=0 表示全量（兼容老调用）。
DEFAULT_PAGE_SIZE = int(os.getenv("LIST_PAGE_SIZE", "200"))

# 登录限流：失败多少次、锁多久、渐进上限
# 旧配置是「错 3 次锁 24 小时」，对单人内网服务来说惩罚过重且无法自助解锁，
# 手抖三次就相当于把自己关在门外一整天。改成短锁 + 翻倍递增：
# 既不放松暴力破解成本，也不会误伤正常使用者。
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "300"))
LOGIN_LOCKOUT_MAX_SECONDS = int(os.getenv("LOGIN_LOCKOUT_MAX_SECONDS", "3600"))
LOGIN_STATE_MAX_ENTRIES = 2000

# 只有放在反向代理后面才应打开：否则 X-Forwarded-For 可被客户端伪造，
# 让攻击者通过伪造不同 IP 绕开锁定。
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

# Vclip 配置（通过 HTTP API 写入，不直接访问 Vclip 的数据库）
VCLIP_API_URL = os.getenv("VCLIP_API_URL", "http://127.0.0.1:4173/api/clips")
VCLIP_ACCESS_PASSWORD = os.getenv("VCLIP_ACCESS_PASSWORD", "")
VCLIP_TIMEOUT_SECONDS = float(os.getenv("VCLIP_TIMEOUT_SECONDS", "5"))

APP_VERSION = "2.1.0"
STARTED_AT = datetime.now(timezone.utc)

admin_login_state: Dict[str, dict] = {}
admin_login_state_lock = Lock()

device_store = DeviceStore(DEVICES_FILE, ttl_days=DEVICE_TOKEN_TTL_DAYS)


class ShareLinkRequest(BaseModel):
    filepath: str
    expire_seconds: int = Field(
        default=DEFAULT_SHARE_EXPIRE_SECONDS,
        ge=1,
        le=MAX_SHARE_EXPIRE_SECONDS,
    )
    max_downloads: int | None = Field(default=MAX_DOWNLOADS, ge=1)


class AdminLoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    remember: bool = True
    device_name: str = Field(default="", max_length=60)


class UnlockRequest(BaseModel):
    ip: str = Field(default="", max_length=64)


# ---------------------------------------------------------------- 工具函数
class UploadTooLarge(Exception):
    """上传体积超过 MAX_UPLOAD_BYTES。用自定义异常区分「超限」和「写入失败」，
    两者对用户是 413 和 400，混成一个会让人以为是磁盘坏了。"""

    def __init__(self, limit_mb: int) -> None:
        super().__init__(f"upload exceeds {limit_mb} MB")
        self.limit_mb = limit_mb


def resolve_safe_path(relative_path: str = "") -> Path:
    candidate = Path(relative_path or "")
    if candidate.is_absolute():
        raise HTTPException(400, "不允许使用绝对路径。")

    resolved = (BASE_DIR / candidate).resolve()
    try:
        resolved.relative_to(BASE_DIR)
    except ValueError as exc:
        raise HTTPException(400, "路径非法。") from exc

    return resolved


def relative_path_for_response(path: Path) -> str:
    try:
        return path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return path.name


def get_client_ip(request: Request) -> str:
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def describe_device(request: Request) -> str:
    """从 User-Agent 里拼一个人类可读的设备名，用于设备列表展示。"""
    ua = (request.headers.get("user-agent") or "").lower()
    if "iphone" in ua:
        platform = "iPhone"
    elif "ipad" in ua:
        platform = "iPad"
    elif "android" in ua:
        platform = "Android"
    elif "mac os x" in ua or "macintosh" in ua:
        platform = "Mac"
    elif "windows" in ua:
        platform = "Windows"
    elif "linux" in ua:
        platform = "Linux"
    else:
        platform = "未知设备"

    browser = ""
    for marker, label in (
        ("edg/", "Edge"),
        ("chrome/", "Chrome"),
        ("firefox/", "Firefox"),
        ("safari/", "Safari"),
    ):
        if marker in ua:
            browser = label
            break

    return f"{platform} · {browser}" if browser else platform


# ---------------------------------------------------------------- 登录状态机
def _login_state(ip: str) -> dict:
    state = admin_login_state.get(ip)
    if state is None:
        # 防止伪造大量来源 IP 把内存喂爆
        if len(admin_login_state) >= LOGIN_STATE_MAX_ENTRIES:
            admin_login_state.clear()
        state = {"failed": 0, "locked_until": None, "level": 0}
        admin_login_state[ip] = state
    return state


def build_locked_response(locked_until: datetime) -> JSONResponse:
    remaining = max(0, int((locked_until - datetime.now(timezone.utc)).total_seconds()))
    minutes = max(1, round(remaining / 60))
    return JSONResponse(
        status_code=423,
        content={
            "detail": f"登录尝试过于频繁，请在约 {minutes} 分钟后重试，或从已登录的设备中解锁。",
            "locked_until": locked_until.isoformat(),
            "retry_after": remaining,
        },
        headers={"Retry-After": str(remaining)},
    )


def build_unauthorized_response() -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "口令无效，请重新输入。"})


def check_admin_lockout(request: Request) -> JSONResponse | None:
    ip = get_client_ip(request)
    now = datetime.now(timezone.utc)

    with admin_login_state_lock:
        state = admin_login_state.get(ip)
        if state is None:
            return None
        locked_until = state["locked_until"]
        if locked_until is None:
            return None
        if locked_until > now:
            return build_locked_response(locked_until)
        # 锁定已过期：恢复可登录，但保留 level 以便下次再犯时延长
        state["locked_until"] = None
        state["failed"] = 0

    return None


def register_failed_login(request: Request) -> JSONResponse:
    ip = get_client_ip(request)
    now = datetime.now(timezone.utc)

    with admin_login_state_lock:
        state = _login_state(ip)
        locked_until = state["locked_until"]
        if locked_until is not None and locked_until > now:
            return build_locked_response(locked_until)

        state["failed"] += 1
        if state["failed"] >= LOGIN_MAX_ATTEMPTS:
            state["level"] += 1
            seconds = min(LOGIN_LOCKOUT_SECONDS * (2 ** (state["level"] - 1)), LOGIN_LOCKOUT_MAX_SECONDS)
            state["locked_until"] = now + timedelta(seconds=seconds)
            state["failed"] = 0
            logger.warning(
                "admin login locked | ip=%s | %ss | level=%s",
                ip,
                seconds,
                state["level"],
            )
            return build_locked_response(state["locked_until"])

    return build_unauthorized_response()


def register_successful_login(request: Request) -> None:
    ip = get_client_ip(request)
    with admin_login_state_lock:
        admin_login_state.pop(ip, None)


def unlock_ip(ip: str) -> list[str]:
    """清除某个 IP（或全部）的锁定状态，返回被清除的 IP 列表。"""
    with admin_login_state_lock:
        if not ip:
            cleared = [key for key, state in admin_login_state.items() if state.get("locked_until")]
            admin_login_state.clear()
            return cleared
        if ip in admin_login_state:
            admin_login_state.pop(ip, None)
            return [ip]
        return []


# ---------------------------------------------------------------- 鉴权
def authenticate_admin(request: Request) -> JSONResponse | None:
    """设备令牌优先，管理员口令兜底。

    浏览器原生下载无法带自定义请求头，所以两者都支持查询参数：
    设备令牌走 ?dt=，管理员口令走 ?token=（兼容旧链接）。
    """
    device_token = request.headers.get("X-Device-Token") or request.query_params.get("dt")
    if device_token and device_store.verify(device_token):
        return None

    provided = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    if not provided:
        return build_unauthorized_response()

    # 常量时间比较，避免时序侧信道
    if not hmac.compare_digest(provided.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")):
        return build_unauthorized_response()

    return None


# ---------------------------------------------------------------- 分享 token
def cleanup_expired_tokens(now: datetime | None = None) -> list[str]:
    """清掉过期链接，返回被清掉的 token 列表。"""
    return share_store.purge_expired(now)


def sync_share_link_to_vclip(share_url: str, expires_at: datetime) -> None:
    """把分享链接推送到 Vclip 剪贴板。

    走 Vclip 的 HTTP API，而不是直接写它的数据库：这样 Vclip 换存储
    （MySQL -> SQLite，或以后换别的）都不需要改这里。
    """
    if not VCLIP_API_URL:
        return

    expires_iso = expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = json.dumps({"content": share_url, "expires_at": expires_iso}).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if VCLIP_ACCESS_PASSWORD:
        credential = base64.b64encode(
            f"vclip:{VCLIP_ACCESS_PASSWORD}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {credential}"

    request_obj = urlrequest.Request(VCLIP_API_URL, data=payload, headers=headers, method="POST")

    try:
        with urlrequest.urlopen(request_obj, timeout=VCLIP_TIMEOUT_SECONDS) as response:
            if response.status not in (200, 201):
                logger.warning("Vclip responded with status %s", response.status)
    except urlerror.HTTPError as exc:
        if exc.code == 401:
            logger.warning(
                "Vclip rejected the request (401). "
                "Check that VCLIP_ACCESS_PASSWORD matches Vclip's ACCESS_PASSWORD."
            )
        else:
            logger.warning("Failed to sync share link to Vclip: HTTP %s %s", exc.code, exc.reason)
    except Exception as exc:  # noqa: BLE001 - 推送失败绝不影响主流程
        logger.warning("Failed to sync share link to Vclip: %s", exc)


# ---------------------------------------------------------------- 安全响应头
# 管理端是单文件 HTML + Vue 运行时编译，inline script 和 eval 都去不掉，
# 所以 CSP 的 script 源必然宽松。它真正的价值在 connect-src / img-src / form-action：
# 即使某个 XSS 拿到令牌，也没有出口把它发出去——只能回连本机。
ADMIN_CSP = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: blob:",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
    ]
)
# 公网端只回下载流和错误页，不需要任何外部资源
PUBLIC_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

# 浏览器自动发起、拿不到自定义请求头的路径：必须免鉴权，否则 PWA 装不上
PWA_EXEMPT = {"/", "/api/auth/login", "/manifest.webmanifest", "/sw.js", "/favicon.ico"}


def attach_security_headers(app: FastAPI, *, csp: str) -> None:
    """补安全响应头与缓存策略。

    Starlette 的 add_middleware 是 insert(0)，也就是**最后注册的在最外层**。
    所以必须在 create_*_app 末尾调用，否则鉴权中间件提前返回的 401/423/403
    会绕过这里，那些响应恰好最需要 no-store。
    """

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        # 分享令牌放在 URL 路径里，Referer 是最容易被忽视的泄漏通道
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Content-Security-Policy", csp)
        headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")

        path = request.url.path
        if path.startswith("/vendor/"):
            headers.setdefault("Cache-Control", "public, max-age=604800")
        elif path.startswith("/static/"):
            # 图标 / manifest 不会天天变，但也不是永远不变——给一天，别学 vendor 给一周
            headers.setdefault("Cache-Control", "public, max-age=86400")
        elif path.startswith("/api/") or path.startswith("/s/"):
            # 带令牌的响应不该留在任何中间缓存里
            headers.setdefault("Cache-Control", "no-store")
        else:
            headers.setdefault("Cache-Control", "no-cache")
        return response


# ---------------------------------------------------------------- 管理端
def create_internal_app() -> FastAPI:
    # 管理端不暴露文档：/docs 与 /openapi.json 会把完整接口清单白送出去
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, title="file-share-server")

    @app.middleware("http")
    async def admin_auth_middleware(request: Request, call_next):
        path = request.url.path
        # PWA 这三样是浏览器自己发起的请求，带不了自定义令牌头。
        # 拦下来只会让 manifest 401、SW 注册失败，然后你在 DevTools 里盯着一个空 manifest 发呆。
        if (
            request.method == "OPTIONS"
            or path in PWA_EXEMPT
            or path.startswith("/static/")
        ):
            return await call_next(request)

        if path.startswith("/api/"):
            locked_response = check_admin_lockout(request)
            if locked_response is not None:
                return locked_response

            token_response = authenticate_admin(request)
            if token_response is not None:
                return token_response

        return await call_next(request)

    # 前端依赖（Vue / Tailwind）放在 vendor/ 走本地静态服务。
    # 原来引用两个公网 CDN——私人服务断网就白屏，这不叫降级，这叫罢工。
    vendor_dir = PROJECT_DIR / "vendor"
    if vendor_dir.is_dir():
        app.mount("/vendor", StaticFiles(directory=str(vendor_dir)), name="vendor")

    # 图标、manifest、SW 走 /static。MIME 比路径重要：
    # manifest 必须是 application/manifest+json，否则 Chrome 会当普通文件下载。
    static_dir = PROJECT_DIR / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    async def manifest():
        path = static_dir / "manifest.webmanifest"
        if not path.exists():
            raise HTTPException(404, "manifest missing")
        return FileResponse(path, media_type="application/manifest+json")

    @app.get("/sw.js", include_in_schema=False)
    async def service_worker():
        path = static_dir / "sw.js"
        if not path.exists():
            raise HTTPException(404, "service worker missing")
        # SW 本身绝不能被缓存：缓存住的 SW 永远不会自己更新
        return FileResponse(
            path,
            media_type="text/javascript",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        path = static_dir / "favicon.ico"
        if not path.exists():
            raise HTTPException(404, "favicon missing")
        return FileResponse(path, media_type="image/x-icon")

    @app.get("/")
    async def index():
        index_path = PROJECT_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(404, "index.html not found in project root")
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/health")
    async def health():
        writable = os.access(BASE_DIR, os.W_OK)
        active_shares = share_store.count()
        uptime = int((datetime.now(timezone.utc) - STARTED_AT).total_seconds())
        return {
            "status": "ok" if writable else "degraded",
            "share_dir_ok": writable,
            "active_shares": active_shares,
            "trusted_devices": len(device_store.list_devices()),
            "upload_limit_mb": MAX_UPLOAD_MB,
            "uptime_seconds": uptime,
            "version": APP_VERSION,
        }

    @app.get("/api/server-info")
    async def server_info():
        """设置页要展示的服务配置。

        这里全部读真实生效的运行时变量，不做任何推测。前端「设置」视图宁可
        少显示几项，也不拿假数字凑版面——那种仪表盘只会让人误判。
        """
        return {
            "share_dir": str(BASE_DIR),
            "share_dir_ok": os.access(BASE_DIR, os.W_OK),
            "admin_host": ADMIN_HOST,
            "admin_port": ADMIN_PORT,
            "public_host": PUBLIC_HOST,
            "public_port": PUBLIC_PORT,
            "public_base_url": PUBLIC_BASE_URL,
            "default_expire_hours": DEFAULT_TOKEN_EXPIRE_HOURS,
            "max_expire_hours": MAX_SHARE_EXPIRE_SECONDS // 3600,
            "default_max_downloads": MAX_DOWNLOADS,
            "upload_limit_mb": MAX_UPLOAD_MB,
            "list_page_size": DEFAULT_PAGE_SIZE,
            "device_token_ttl_days": DEVICE_TOKEN_TTL_DAYS,
            "vclip_enabled": bool(VCLIP_API_URL),
            "qrcode_available": qrcode is not None,
            "version": APP_VERSION,
        }

    @app.get("/api/qr")
    async def qr_code(data: str):
        """把任意文本编码成 SVG 二维码。

        前端不画二维码，原因很简单：二维码编码（Reed-Solomon 纠错、掩码选择）
        自己实现容易生成「看起来像二维码但扫不出来」的图案，而这种失败只有拿
        手机真扫才发现。交给成熟库，前端只负责显示。

        用 SVG 而不是 PNG：矢量，任意尺寸都清晰，且不受设备像素比影响。
        """
        if not data:
            raise HTTPException(400, "二维码内容不能为空。")
        if len(data) > 2048:
            raise HTTPException(400, "二维码内容过长。")
        if qrcode is None:
            raise HTTPException(503, "服务端未安装 qrcode，无法生成二维码。")

        image = qrcode.make(data, image_factory=qr_svg.SvgPathImage, box_size=10, border=2)
        buffer = io.BytesIO()
        image.save(buffer)
        svg = buffer.getvalue().decode("utf-8")

        # 库输出的是物理毫米尺寸（随二维码版本变化，不一定是 33mm）；改成撑满
        # 容器，由 CSS 决定显示多大。用正则而不是写死字符串，否则内容一变长度
        # 尺寸就对不上，只剩一半图案。
        # 二维码必须保持深色模块 + 浅色底，不能跟随主题反色，否则扫码率会掉。
        svg = re.sub(r'(width|height)="\d+(?:\.\d+)?mm"', r'\1="100%"', svg)
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/auth/login")
    async def admin_login(payload: AdminLoginRequest, request: Request):
        locked_response = check_admin_lockout(request)
        if locked_response is not None:
            return locked_response

        if not hmac.compare_digest(payload.token.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")):
            return register_failed_login(request)

        register_successful_login(request)

        result = {"ok": True, "device_token": None, "device_id": None, "expires_at": None}
        if payload.remember:
            name = payload.device_name.strip() or describe_device(request)
            token, device_id, expires_at = device_store.issue(name)
            result.update(
                device_token=token,
                device_id=device_id,
                expires_at=expires_at,
                device_name=name,
            )
            logger.info("device trusted | id=%s | name=%s | ip=%s", device_id, name, get_client_ip(request))

        return result

    @app.post("/api/auth/unlock")
    async def admin_unlock(payload: UnlockRequest):
        """从另一台已登录设备上解除某个 IP 的锁定。

        典型场景：手机上输错几次把家里出口 IP 锁了，用已经记住的平板解锁。
        """
        cleared = unlock_ip(payload.ip.strip())
        if cleared:
            logger.info("admin lockout cleared for %s", ", ".join(cleared))
        return {"unlocked": cleared}

    @app.get("/api/devices")
    async def list_devices():
        return {"devices": device_store.list_devices()}

    @app.delete("/api/devices/{device_id}")
    async def revoke_device(device_id: str):
        if not device_store.revoke(device_id):
            raise HTTPException(404, "设备不存在或已被移除。")
        logger.info("device revoked | id=%s", device_id)
        return {"revoked": device_id}

    @app.get("/api/list")
    @app.get("/api/list/{path:path}")
    async def list_files(path: str = "", limit: int = -1, offset: int = 0):
        """目录列表。folders 全量返回，files 分页返回。

        分页只作用在文件上：一个目录里的子目录通常几个到几十个，全发出去
        不会疼；真正撑爆响应的是几千个文件条目。
        """
        target_dir = resolve_safe_path(path)
        if not target_dir.exists() or not target_dir.is_dir():
            raise HTTPException(404, "目录不存在。")

        files = []
        folders = []

        for entry in target_dir.iterdir():
            try:
                stat = entry.stat()
            except OSError:
                # 单个条目读不到（权限 / 断链 / 网络盘抖动）不该让整页 500
                continue
            item = {
                "name": entry.name,
                "path": relative_path_for_response(entry),
                "mtime": stat.st_mtime,
            }
            if entry.is_file():
                files.append({**item, "size": stat.st_size, "type": "file"})
            elif entry.is_dir():
                folders.append({**item, "type": "folder"})

        # 稳定排序：文件多时前端「加载更多」才有确定顺序，
        # 排序还让 SMB 目录的 iterdir 抖动不会导致条目在分页间重复/漏掉。
        folders.sort(key=lambda item: item["name"].lower())
        files.sort(key=lambda item: item["name"].lower())

        total_files = len(files)
        page_size = DEFAULT_PAGE_SIZE if limit < 0 else limit
        start = max(0, offset)
        if page_size > 0:
            page = files[start : start + page_size]
        else:
            page = files[start:]
        next_offset = start + len(page)

        return {
            "path": relative_path_for_response(target_dir) if path else "",
            "folders": folders,
            "files": page,
            "total_files": total_files,
            "total_folders": len(folders),
            "offset": start,
            "limit": page_size,
            "next_offset": next_offset,
            "has_more": next_offset < total_files,
        }

    @app.get("/api/download/{filepath:path}")
    async def download_file(filepath: str):
        file_path = resolve_safe_path(filepath)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "文件不存在。")

        return FileResponse(
            file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    @app.post("/api/upload")
    async def upload_file(file: UploadFile = File(...), path: str = ""):
        target_dir = resolve_safe_path(path)
        if not target_dir.exists() or not target_dir.is_dir():
            raise HTTPException(404, "目标目录不存在。")

        safe_name = Path(file.filename or "").name
        if not safe_name:
            raise HTTPException(400, "文件名非法。")

        target_file = resolve_safe_path(str(Path(path) / safe_name))
        if not ALLOW_OVERWRITE and target_file.exists():
            raise HTTPException(400, "同名文件已存在，且未开启覆盖。")

        # 分块写入：每次只把 1MB 读入内存，避免大文件一次性占满服务器内存
        chunk_size = 1024 * 1024
        written = 0
        try:
            with open(target_file, "wb") as output:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    written += len(chunk)
                    # 体积上限在写入过程中判定，而不是先落盘再看大小：
                    # 事后判断意味着一个 80GB 的误拖文件已经把你的盘写满了。
                    if MAX_UPLOAD_BYTES and written > MAX_UPLOAD_BYTES:
                        raise UploadTooLarge(MAX_UPLOAD_MB)
                    output.write(chunk)
        except UploadTooLarge:
            try:
                target_file.unlink(missing_ok=True)
            except OSError:
                pass
            logger.warning("upload rejected | too large | target=%s", target_file)
            raise HTTPException(413, f"文件超过 {MAX_UPLOAD_MB} MB 上限。") from None
        except OSError as exc:
            # 非法文件名（Windows 上的 < > | 等）、磁盘满、权限不足
            # 以前这里会漏成 500 并留下半个残文件，现在统一收口
            logger.warning("upload failed | target=%s | %s", target_file, exc)
            try:
                target_file.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(400, f"写入失败：{exc.strerror or exc}") from exc

        return {"uploaded": safe_name, "path": path, "size": written}

    @app.post("/api/share-link")
    async def create_share_link(payload: ShareLinkRequest, background_tasks: BackgroundTasks):
        file_path = resolve_safe_path(payload.filepath)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "文件不存在。")

        cleanup_expired_tokens()
        token = token_hex(16)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expire_seconds)

        # 存相对路径，不存绝对路径：换盘 / 换机器后旧链接仍然指得对
        share_store.add(
            token,
            filepath=relative_path_for_response(file_path),
            expires_at=expires_at,
            max_downloads=payload.max_downloads,
        )

        share_url = f"{PUBLIC_BASE_URL}/s/{token}"
        background_tasks.add_task(sync_share_link_to_vclip, share_url, expires_at)

        return {
            "token": token,
            "expires_at": expires_at.isoformat(),
            "download_url": share_url,
        }

    @app.get("/api/shares")
    async def list_shares():
        cleanup_expired_tokens()
        return [
            {
                "token": item["token"],
                "filepath": item["filepath"],
                "expires_at": item["expires_at"],
                "max_downloads": item["max_downloads"],
                "download_count": item["download_count"],
                "downloads": item["downloads"],
            }
            for item in share_store.list_all()
        ]

    @app.delete("/api/shares/{token}")
    async def revoke_share(token: str):
        """手动作废一条链接。之前只能等它自然过期。"""
        if not share_store.remove(token):
            raise HTTPException(404, "分享链接不存在。")
        logger.info("share revoked | token=%s", token)
        return {"revoked": token}

    attach_security_headers(app, csp=ADMIN_CSP)
    return app


# ---------------------------------------------------------------- 公网端
def create_public_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def public_route_guard(request: Request, call_next):
        path = request.url.path
        # 公网端只放行两条路：按 token 下载，以及给监控用的 /health。
        # 其余一律 403，连「这个服务存在」都不承认。
        if path != "/health" and not path.startswith("/s/"):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)

    @app.get("/health")
    async def public_health():
        return {"status": "ok", "version": APP_VERSION}

    @app.get("/s/{token}")
    async def download_shared_file(token: str, request: Request):
        client_ip = get_client_ip(request)

        info = share_store.get(token)
        if not info:
            raise HTTPException(404, "分享链接不存在或已失效。")

        # 存的是相对路径，落地前仍然要走一遍安全解析：
        # shares.json 是本地文件，但「本地文件也可能被人手改」不是不校验的理由。
        try:
            file_path = resolve_safe_path(info["filepath"])
        except HTTPException as exc:
            raise HTTPException(404, "分享链接不存在或已失效。") from exc

        # 先确认文件真的还在，再计数。
        # 旧实现先 +1 后校验，导致「访问一个文件已被删除的链接」也消耗一次额度，
        # 极端情况下能把 max_downloads 烧光，链接还没被真正下载过一次。
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "文件不存在或被移动。")

        if info["download_count"] >= info["max_downloads"]:
            share_store.remove(token)
            raise HTTPException(404, "分享链接不存在或已失效。")

        counted = share_store.record_download(token, client_ip)
        if not counted:
            raise HTTPException(404, "分享链接不存在或已失效。")

        logger.info(
            "download | token=%s | ip=%s | file=%s | count=%s/%s",
            token,
            client_ip,
            file_path.name,
            counted["download_count"],
            counted["max_downloads"],
        )

        return FileResponse(
            file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    attach_security_headers(app, csp=PUBLIC_CSP)
    return app


app_internal = create_internal_app()
app_public = create_public_app()
