# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from secrets import token_hex
from threading import Lock
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field


app = FastAPI()

load_dotenv()

SHARE_DIR = os.getenv("SHARE_DIR", "shared")
BASE_DIR = Path(SHARE_DIR).resolve()
BASE_DIR.mkdir(exist_ok=True, parents=True)

ALLOW_OVERWRITE = os.getenv("ALLOW_OVERWRITE", "false").lower() == "true"
DEFAULT_SHARE_EXPIRE_SECONDS = 3600
MAX_SHARE_EXPIRE_SECONDS = 7 * 24 * 3600

share_tokens: Dict[str, dict] = {}
share_tokens_lock = Lock()


class ShareLinkRequest(BaseModel):
    filepath: str
    expire_seconds: int = Field(
        default=DEFAULT_SHARE_EXPIRE_SECONDS,
        ge=1,
        le=MAX_SHARE_EXPIRE_SECONDS,
    )


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


def cleanup_expired_tokens(now: datetime | None = None) -> None:
    current_time = now or datetime.now(timezone.utc)
    expired = []

    with share_tokens_lock:
        for token, payload in share_tokens.items():
            if payload["expires_at"] <= current_time:
                expired.append(token)

        for token in expired:
            share_tokens.pop(token, None)


@app.get("/")
async def index():
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "index.html not found in project root")

    with open(index_path, encoding="utf-8") as file_obj:
        return HTMLResponse(file_obj.read())


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
        }

    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "download_url": f"/s/{token}",
    }


@app.get("/s/{token}")
async def download_shared_file(token: str):
    cleanup_expired_tokens()

    with share_tokens_lock:
        payload = share_tokens.get(token)

    if not payload:
        raise HTTPException(404, "Share link not found.")

    file_path = payload["file_path"]
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "File not found.")

    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
