# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import hmac
import os
from pathlib import Path
from secrets import token_hex
from threading import Lock
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field


load_dotenv()

SHARE_DIR = os.getenv("SHARE_DIR", "shared")
BASE_DIR = Path(SHARE_DIR).resolve()
BASE_DIR.mkdir(exist_ok=True, parents=True)

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN") or os.getenv("admin_token")
if not ADMIN_TOKEN:
    raise RuntimeError("ADMIN_TOKEN/admin_token is required.")

ADMIN_HOST = os.getenv("ADMIN_HOST", "0.0.0.0")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8800"))
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "0.0.0.0")
PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", "9900"))
ALLOW_OVERWRITE = os.getenv("ALLOW_OVERWRITE", "false").lower() == "true"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://221.11.22.70:9900").rstrip("/")
DEFAULT_TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))
DEFAULT_SHARE_EXPIRE_SECONDS = DEFAULT_TOKEN_EXPIRE_HOURS * 3600
MAX_SHARE_EXPIRE_SECONDS = 7 * 24 * 3600
MAX_FAILED_LOGIN_ATTEMPTS = 3
ADMIN_LOCKOUT_SECONDS = 24 * 3600

share_tokens: Dict[str, dict] = {}
share_tokens_lock = Lock()
admin_login_state: Dict[str, dict] = {}
admin_login_state_lock = Lock()


class ShareLinkRequest(BaseModel):
    filepath: str
    expire_seconds: int = Field(
        default=DEFAULT_SHARE_EXPIRE_SECONDS,
        ge=1,
        le=MAX_SHARE_EXPIRE_SECONDS,
    )


class AdminLoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


def resolve_safe_path(relative_path: str = "") -> Path:
    candidate = Path(relative_path or "")
    if candidate.is_absolute():
        raise HTTPException(400, "Absolute paths are not allowed.")

    resolved = (BASE_DIR / candidate).resolve()
    try:
        resolved.relative_to(BASE_DIR)
    except ValueError as exc:
        raise HTTPException(400, "Invalid path.") from exc

    return resolved


def relative_path_for_response(path: Path) -> str:
    return path.relative_to(BASE_DIR).as_posix()


def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def get_admin_state(ip: str, now: datetime | None = None) -> dict:
    current_time = now or datetime.now(timezone.utc)
    with admin_login_state_lock:
        state = admin_login_state.setdefault(
            ip,
            {
                "failed_attempts": 0,
                "locked_until": None,
            },
        )
        locked_until = state["locked_until"]
        if locked_until is not None and locked_until <= current_time:
            state["failed_attempts"] = 0
            state["locked_until"] = None
        return state


def build_locked_response(locked_until: datetime) -> JSONResponse:
    return JSONResponse(
        status_code=423,
        content={
            "detail": "Admin access is temporarily locked.",
            "locked_until": locked_until.isoformat(),
        },
    )


def build_unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid admin token."},
    )


def check_admin_lockout(request: Request) -> JSONResponse | None:
    client_ip = get_client_ip(request)
    state = get_admin_state(client_ip)
    locked_until = state["locked_until"]
    if locked_until is not None:
        return build_locked_response(locked_until)
    return None


def check_admin_token(request: Request) -> JSONResponse | None:
    provided_token = request.headers.get("X-Admin-Token")
    if not provided_token:
        return build_unauthorized_response()

    if not hmac.compare_digest(provided_token, ADMIN_TOKEN):
        return build_unauthorized_response()

    return None


def register_failed_login(request: Request) -> JSONResponse:
    client_ip = get_client_ip(request)
    now = datetime.now(timezone.utc)

    with admin_login_state_lock:
        state = admin_login_state.setdefault(
            client_ip,
            {
                "failed_attempts": 0,
                "locked_until": None,
            },
        )
        if state["locked_until"] is not None and state["locked_until"] > now:
            return build_locked_response(state["locked_until"])

        state["failed_attempts"] += 1
        if state["failed_attempts"] >= MAX_FAILED_LOGIN_ATTEMPTS:
            state["locked_until"] = now + timedelta(seconds=ADMIN_LOCKOUT_SECONDS)
            state["failed_attempts"] = 0
            return build_locked_response(state["locked_until"])

    return build_unauthorized_response()


def register_successful_login(request: Request) -> None:
    client_ip = get_client_ip(request)
    with admin_login_state_lock:
        admin_login_state.pop(client_ip, None)


def cleanup_expired_tokens(now: datetime | None = None) -> None:
    current_time = now or datetime.now(timezone.utc)
    expired = []

    with share_tokens_lock:
        for token, payload in share_tokens.items():
            if payload["expires_at"] <= current_time:
                expired.append(token)

        for token in expired:
            share_tokens.pop(token, None)


def create_internal_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def admin_auth_middleware(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path == "/" or request.url.path == "/api/auth/login":
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            locked_response = check_admin_lockout(request)
            if locked_response is not None:
                return locked_response

            token_response = check_admin_token(request)
            if token_response is not None:
                return token_response

        return await call_next(request)

    @app.get("/")
    async def index():
        index_path = Path(__file__).parent / "index.html"
        if not index_path.exists():
            raise HTTPException(404, "index.html not found in project root")

        with open(index_path, encoding="utf-8") as file_obj:
            return HTMLResponse(file_obj.read())

    @app.post("/api/auth/login")
    async def admin_login(payload: AdminLoginRequest, request: Request):
        locked_response = check_admin_lockout(request)
        if locked_response is not None:
            return locked_response

        if not hmac.compare_digest(payload.token, ADMIN_TOKEN):
            return register_failed_login(request)

        register_successful_login(request)
        return {"ok": True}

    @app.get("/api/list")
    @app.get("/api/list/{path:path}")
    async def list_files(path: str = ""):
        target_dir = resolve_safe_path(path)
        if not target_dir.exists() or not target_dir.is_dir():
            raise HTTPException(404, "Directory not found.")

        files = []
        folders = []

        for entry in target_dir.iterdir():
            if entry.is_file():
                files.append(
                    {
                        "name": entry.name,
                        "path": relative_path_for_response(entry),
                        "size": entry.stat().st_size,
                        "mtime": entry.stat().st_mtime,
                        "type": "file",
                    }
                )
            elif entry.is_dir():
                folders.append(
                    {
                        "name": entry.name,
                        "path": relative_path_for_response(entry),
                        "mtime": entry.stat().st_mtime,
                        "type": "folder",
                    }
                )

        return {
            "path": relative_path_for_response(target_dir) if path else "",
            "folders": folders,
            "files": files,
        }

    @app.get("/api/download/{filepath:path}")
    async def download_file(filepath: str):
        file_path = resolve_safe_path(filepath)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "File not found.")

        return FileResponse(
            file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    @app.post("/api/upload")
    async def upload_file(file: UploadFile = File(...), path: str = ""):
        target_dir = resolve_safe_path(path)
        if not target_dir.exists() or not target_dir.is_dir():
            raise HTTPException(404, "Target directory not found.")

        safe_name = Path(file.filename or "").name
        if not safe_name:
            raise HTTPException(400, "Invalid filename.")

        target_file = resolve_safe_path(str(Path(path) / safe_name))
        if not ALLOW_OVERWRITE and target_file.exists():
            raise HTTPException(400, "Overwrite disabled.")

        with open(target_file, "wb") as output:
            content = await file.read()
            output.write(content)

        return {"uploaded": safe_name, "path": path}

    @app.post("/api/share-link")
    async def create_share_link(payload: ShareLinkRequest):
        file_path = resolve_safe_path(payload.filepath)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "File not found.")

        cleanup_expired_tokens()
        token = token_hex(16)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expire_seconds)

        with share_tokens_lock:
            share_tokens[token] = {
                "file_path": file_path,
                "expires_at": expires_at,
                "download_count": 0,
                "downloads": [],
            }

        return {
            "token": token,
            "expires_at": expires_at.isoformat(),
            "download_url": f"{PUBLIC_BASE_URL}/s/{token}",
        }

    @app.get("/api/shares")
    async def list_shares():
        cleanup_expired_tokens()
        results = []
        with share_tokens_lock:
            for token, payload in share_tokens.items():
                results.append({
                    "token": token,
                    "filepath": relative_path_for_response(payload["file_path"]),
                    "expires_at": payload["expires_at"].isoformat(),
                    "download_count": payload["download_count"],
                    "downloads": payload["downloads"],
                })
        return results

    return app


def create_public_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def public_route_guard(request: Request, call_next):
        if not request.url.path.startswith("/s/"):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)

    @app.get("/s/{token}")
    async def download_shared_file(token: str, request: Request):
        cleanup_expired_tokens()
        client_ip = get_client_ip(request)
        now = datetime.now(timezone.utc)

        with share_tokens_lock:
            payload = share_tokens.get(token)
            if not payload:
                raise HTTPException(404, "Share link not found.")

            # Update stats
            payload["download_count"] += 1
            payload["downloads"].append({
                "ip": client_ip,
                "time": now.isoformat()
            })
            # Keep last 10 logs
            if len(payload["downloads"]) > 10:
                payload["downloads"].pop(0)

            file_path = payload["file_path"]
            expires_at = payload["expires_at"]

        print(f"[DOWNLOAD] {now.strftime('%Y-%m-%d %H:%M:%S')} | Token: {token} | IP: {client_ip} | File: {file_path.name} | Total: {payload['download_count']}")

        if expires_at <= now:
            with share_tokens_lock:
                share_tokens.pop(token, None)
            raise HTTPException(404, "Share link not found.")

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(404, "File not found.")

        return FileResponse(
            file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    return app


app_internal = create_internal_app()
app_public = create_public_app()
