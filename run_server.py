#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import socket
import sys

import uvicorn
from dotenv import load_dotenv

from filesvc_api import ADMIN_HOST
from filesvc_api import ADMIN_PORT
from filesvc_api import PUBLIC_HOST
from filesvc_api import PUBLIC_PORT
from filesvc_api import SHARE_DIR


def build_server(app_path: str, host: str, port: int) -> uvicorn.Server:
    config = uvicorn.Config(
        app_path,
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
    return uvicorn.Server(config)


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


async def run_servers():
    admin_server = build_server("filesvc_api:app_internal", ADMIN_HOST, ADMIN_PORT)
    public_server = build_server("filesvc_api:app_public", PUBLIC_HOST, PUBLIC_PORT)

    admin_server.install_signal_handlers = lambda: None
    public_server.install_signal_handlers = lambda: None

    print("=" * 50)
    print("File Share Server")
    print("=" * 50)
    print(f"Share directory: {SHARE_DIR}")
    print(f"Internal admin: http://{ADMIN_HOST}:{ADMIN_PORT}")
    print(f"Public download: http://{PUBLIC_HOST}:{PUBLIC_PORT}")
    print("-" * 50)
    print("Ports:")
    print(f"[{ADMIN_PORT}] admin interface with token auth")
    print(f"[{PUBLIC_PORT}] public download only")
    print("=" * 50)

    await asyncio.gather(
        admin_server.serve(),
        public_server.serve(),
    )


if __name__ == "__main__":
    load_dotenv()

    if not is_port_available(ADMIN_HOST, ADMIN_PORT):
        print(f"[ERROR] Port {ADMIN_HOST}:{ADMIN_PORT} is already in use.")
        sys.exit(1)

    if not is_port_available(PUBLIC_HOST, PUBLIC_PORT):
        print(f"[ERROR] Port {PUBLIC_HOST}:{PUBLIC_PORT} is already in use.")
        sys.exit(1)

    asyncio.run(run_servers())
