# -*- coding: utf-8 -*-
"""
Created on Thu Dec 11 16:50:06 2025

@author: leying_IT
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv



app = FastAPI()

# 加载.env文件
load_dotenv()

# 从环境变量读取共享目录，默认为当前目录下的shared文件夹
SHARE_DIR = os.getenv("SHARE_DIR", "shared")
BASE_DIR = Path(SHARE_DIR)
BASE_DIR.mkdir(exist_ok=True, parents=True)

print(">>> REAL BASE_DIR:", BASE_DIR.resolve())
print(">>> SHARE_DIR from .env:", SHARE_DIR)


ALLOW_OVERWRITE = False



@app.get("/")
async def index():
    # index.html现在在项目根目录，不在共享目录中
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "index.html not found in project root")
    with open(index_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/list")
@app.get("/api/list/{path:path}")
async def list_files(path: str = ""):
    target_dir = BASE_DIR / path
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(404, "Directory not found.")
    
    files = []
    folders = []
    
    for f in target_dir.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "mtime": f.stat().st_mtime,
                "type": "file"
            })
        elif f.is_dir():
            folders.append({
                "name": f.name,
                "mtime": f.stat().st_mtime,
                "type": "folder"
            })
    
    return {
        "path": path,
        "folders": folders,
        "files": files
    }

@app.get("/api/download/{filepath:path}")
async def download_file(filepath: str):
    file_path = BASE_DIR / filepath
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(file_path, filename=file_path.name,media_type="application/octet-stream")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), path: str = ""):
    target_dir = BASE_DIR / path
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(404, "Target directory not found.")
    
    filename = target_dir / file.filename
    print(">>> Upload to:", filename.resolve())
    if not ALLOW_OVERWRITE and filename.exists():
        raise HTTPException(400, "Overwrite disabled.")

    with open(filename, "wb") as out:
        content = await file.read()
        out.write(content)

    return {"uploaded": file.filename, "path": path}
