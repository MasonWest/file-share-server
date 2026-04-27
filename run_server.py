#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import uvicorn
from dotenv import load_dotenv


if __name__ == "__main__":
    load_dotenv()

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8800"))
    share_dir = os.getenv("SHARE_DIR", "shared")

    print("=" * 50)
    print("File Share Server")
    print("=" * 50)
    print(f"Share directory: {share_dir}")
    print(f"Server address: {host}:{port}")
    print(f"Local URL: http://localhost:{port}")
    print(f"LAN URL: http://[your-ip]:{port}")
    print("-" * 50)
    print("Features:")
    print("[OK] File upload and download")
    print("[OK] Folder browsing")
    print("[OK] File sorting")
    print("[OK] Path navigation")
    print("-" * 50)
    print("Press Ctrl+C to stop the server")
    print("=" * 50)

    uvicorn.run(
        "filesvc_api:app",
        host=host,
        port=port,
        reload=False,
    )
